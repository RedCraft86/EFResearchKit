"""Authenticate the producer and state machine of Mastering's shared histories.

The selected effect's context pointer keys parallel native vectors. Setup, a
reset callback, Execute and the global callback have different ownership roles.
Their static joins do not establish public counter names, callback scheduling,
allocator recovery or a complete concurrent lifetime protocol.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_context_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_context_native.json").read_text(encoding="utf-8"))


def _local_storage_plan(present, optional_flag, failed_mask, format_result=0, previous_ready=0):
    """Independent null-guard, request and partial-failure model.

    ``present`` follows the contract's main-pointer order. Failure bits name
    allocation positions, including the unconditionally requested optional slot.
    No allocator capacity or helper side effects are assumed by this model.
    """
    pointers = list(present); requests = []
    if not pointers[0]:
        requests.append(32); pointers[0] = not (failed_mask & 1)
        if not pointers[0]:
            return dict(requests=requests, mainPresent=pointers, formatCalled=False,
                        result=0x8080000a, ready=previous_ready)
    for index, offset in enumerate((0, 8, 16), 1):
        if not pointers[index]:
            requests.append(offset); pointers[index] = not (failed_mask & (1 << index))
    if not all(pointers):
        return dict(requests=requests, mainPresent=pointers, formatCalled=False,
                    result=0x8080000a, ready=previous_ready)
    if optional_flag == 1:
        requests.append(24)
        if failed_mask & 16:
            return dict(requests=requests, mainPresent=pointers, formatCalled=False,
                        result=0x8080000a, ready=previous_ready)
    return dict(requests=requests, mainPresent=pointers, formatCalled=True,
                result=format_result, ready=previous_ready if format_result else 1)


def validate_mastering_context(contract, parent, consumer_contract, consumer, shared, image_base, read, descriptor_contract):
    def equal(check, expected, actual, offset=0):
        if expected != actual:
            raise EffectUpdateError("masteringContext", check, offset, expected, actual)

    equal("schema", "endfield.wwise-mastering-context-native-contract.v6", contract["schema"])
    equal("reviewStatus", "reviewed", contract["status"])
    equal("inputs", parent["nativeInputs"], contract["nativeInputs"])
    equal("consumerInputs", contract["nativeInputs"], consumer_contract["nativeInputs"])
    equal("consumerProof", "validated", consumer["status"])
    equal("descriptorInputs", contract["nativeInputs"], descriptor_contract["nativeInputs"])
    equal("descriptorSchema","endfield.wwise-mastering-gain-native-contract.v3",descriptor_contract['schema'])
    equal("descriptorReviewStatus","reviewed",descriptor_contract['status'])
    equal("sharedProof", "validated", shared["status"])
    equal("boundary", "conditional", contract["evidenceBoundary"])
    methods = contract["methods"]; bodies = {}; resolved = {}
    equal("methodSet", {"init", "prepare", "refresh", "execute", "status", "trigger", "globalCallback", "terminate",
                        "growKeys", "growStatus", "growRecords", "bufferSetup"}, set(methods))
    for name, row in methods.items():
        if name in {"init", "prepare", "refresh", "execute"}:
            equal("consumerMethod:" + name, name, row["consumerMethod"])
            source = consumer_contract["methods"][name]
        else:
            source = row
        rva = int(source["rva"], 16); size = source["bodyLength"]
        equal("extent:" + name, True, type(size) is int and 0 < size <= 4096)
        body = read(rva, size); equal("length:" + name, size, len(body))
        equal("hash:" + name, source["bodySha256"], hashlib.sha256(body).hexdigest())
        bodies[name] = body; resolved[name] = rva
    groups = dict(method=resolved, global_={k: int(v["rva"], 16) for k, v in contract["globals"].items()},
                  data={k: int(v["rva"], 16) for k, v in contract["data"].items()},
                  external={k: int(v["rva"], 16) for k, v in contract["externalEntries"].items()})
    groups["global"] = groups.pop("global_")
    equal("vectorSet", {"keyVector", "statusVector", "recordVector"}, set(contract["globals"]))
    for row in contract["globals"].values():
        equal("vectorHeaderExtent", 24, row["byteLength"])
    for witness, role, displacement in (("contextLookupCount", "keyVector", 16), ("contextLookupTable", "keyVector", 8),
                                       ("contextRecordBase", "recordVector", 8)):
        row = consumer_contract["witnesses"][witness]
        rva = resolved["execute"] + row["bodyOffset"]
        raw = bytes.fromhex(row["instructionHex"])
        equal("vectorConsumerJoin:" + role, groups["global"][role] + displacement,
              rva + len(raw) + int.from_bytes(raw[-4:], "little", signed=True))
    for name, row in contract["data"].items():
        if row.get("evidenceBoundary") == "addressOnly":
            continue
        size = row["byteLength"]
        equal("dataExtent:" + name, True, type(size) is int and 0 < size <= 16)
        raw = bytes.fromhex(row["bytesHex"])
        equal("dataLength:" + name, size, len(raw))
        equal("dataBytes:" + name, raw, read(int(row["rva"], 16), size))
    scale = contract["data"]["durationScale"]
    equal("durationScale", struct.pack("<f", 0.05), read(int(scale["rva"], 16), 4))
    equal("durationScaleDeclaration", struct.pack("<f", 0.05).hex(), scale["bytesHex"])
    from scripts.game_data.il2cpp.pe_imports import resolve_named_import_slots

    equal("importDeclarations", dict(lockEnterImport=dict(library="KERNEL32.dll", symbol="EnterCriticalSection"),
                                    lockLeaveImport=dict(library="KERNEL32.dll", symbol="LeaveCriticalSection")), contract["imports"])
    dos = read(0, 64); pe = struct.unpack_from("<I", dos, 60)[0]
    equal("importHeaderBound", True, 64 <= pe <= 1048576)
    coff = read(pe, 24); optional_size = struct.unpack_from("<H", coff, 20)[0]
    equal("importOptionalBound", True, 112 <= optional_size <= 4096)
    opened = SimpleNamespace(buf=read(0, pe + 24 + optional_size), image_base=image_base,
                             bytes_at_va=lambda va, size: read(va - image_base, size))
    slots = {name: groups["data"][name] for name in contract["imports"]}
    imported = resolve_named_import_slots(opened, slots.values())
    for name, slot in slots.items():
        row = next(v for v in imported["selectedImports"] if v["slotRva"] == slot)
        equal("importName:" + name, (contract["imports"][name]["library"], contract["imports"][name]["symbol"]),
              (row["libraryName"], row["symbolName"]))
    for name, row in methods.items():
        cursor = 0; body = bodies[name]
        for step in row["program"]:
            equal("coverage:" + name, cursor, step["offset"], cursor)
            if "bytesHex" in step:
                raw = bytes.fromhex(step["bytesHex"])
                equal("nonempty:" + name, True, bool(raw), cursor)
                equal("program:" + name, raw, body[cursor:cursor + len(raw)], cursor)
                cursor += len(raw)
                continue
            prefix = bytes.fromhex(step["prefixHex"]); suffix = bytes.fromhex(step["suffixHex"])
            end = cursor + len(prefix) + 4 + len(suffix); raw = body[cursor:end]
            equal("relativeLength:" + name, end - cursor, len(raw), cursor)
            equal("relativeOpcode:" + name, prefix, raw[:len(prefix)], cursor)
            equal("relativeSuffix:" + name, suffix, raw[len(prefix) + 4:], cursor)
            actual = resolved[name] + end + struct.unpack_from("<i", raw, len(prefix))[0]
            equal("relativeJoin:" + name, groups[step["targetKind"]][step["target"]] + step["targetOffset"], actual, cursor)
            cursor = end
        equal("programEnd:" + name, len(body), cursor, cursor)

    def block(name, offset, encoded):
        raw = bytes.fromhex(encoded)
        equal("stateMachine:" + name, raw, bodies[name][offset:offset + len(raw)], offset)

    # Independent field/control-flow grammar. Edited hashes and a re-declared
    # byte program alone cannot promote a changed counter or ownership claim.
    block("status", 0, "4883ec28488b4920488b01ff5008488b08488b91d0000000488bc84883c42848ffe2")
    block("init", 4, "4c8949104d8bd04c8b4c2450488951184c8941204c898120040000")
    block("init", 0x92, "448981e00300000fb6420c8881ec030000837a04000f97c08881ed0300008b42048981f0030000")
    block("trigger", 0x3d, "8bf8")
    block("trigger", 0x4f, "2bc3488b5c243083f8017511486bd768")
    block("trigger", 0x66, "8b423889423c488b7c2420b8010000004883c428c3b8010000004883c428c3")
    block("prepare", 0xd1, "83c00383e0fc")
    block("prepare", 0xed, "8983e8030000c1e00a8bf8c783e403000004000000")
    block("prepare", 0x290, "48393874094883c008483bc175f2")
    block("prepare", 0x3b4, "486bd068")
    block("prepare", 0x3cb, "0f57c033c00f11020f1142100f1142204889423048c7423800020000896a4048896a4848896a5048896a58896a60")
    block("prepare", 0x445, "48837c2e58007579894c2e60488d14cd000000004c89742e48")
    block("prepare", 0x488, "4a8d14a500000000")
    block("prepare", 0x4c6, "394c2e600f848b000000488b542e504c8d04cd00000000894c2e60")
    block("prepare", 0x501, "4889442e504885c07446")
    block("prepare", 0x530, "4889442e58")
    block("prepare", 0x535, "4885c07521498b06498bce488b542e50ff501048c7442e5000000000")
    block("prepare", 0x551, "b802000000e99b010000")
    block("prepare", 0x624, "418b4500")
    block("prepare", 0x636, "0f57c0448bdf4d6bd368f3480f2ac0")
    block("prepare", 0x64d, "43896c0a3cf3480f2cc0ffc88bc8d1e90bc88bc1c1e8020bc18bc8c1e9040bc88bd1c1ea080bd18bc2c1e8100bc2ba10230000ffc04389440a38")
    block("refresh", 0xdd, "498b0424ff50402bc383f8010f8442010000")
    block("refresh", 0xff, "897b3c0f11030f1143100f11432048894330")
    block("refresh", 0x111, "488b4b504885c9740f448b436033d241c1e003")
    block("refresh", 0x129, "488b4b584885c9740f448b436033d241c1e002")
    block("execute", 0xa4, "488bcf488d1c98488b07ff5040")
    block("execute", 0xb8, "8903")
    block("globalCallback", 0xe, "83fa017538")
    block("globalCallback", 0x16, "488d15e3ffffff33ff41b9ba00000048897c24304533c0c7442428800000004889542420b203ff5040")
    block("globalCallback", 0x4b, "81fa800000000f8514010000")
    block("globalCallback", 0x80, "8bc3486bf0684803f24c8b4e584d85c97435")
    block("globalCallback", 0x92, "488b4e48498bd1488b01ff5010488b4e48488b5650488b01ff501048897e5848897e5048897e48")
    block("globalCallback", 0x155, "498b06488d15a1feffff41b880000000498bceff5048")
    block("terminate", 0x3b, "48897328488b93f80300004885d27410488b07488bcfff50104889b3f8030000")
    block("terminate", 0x70, "4889b300040000488b93080400004885d27410488b07488bcfff50104889b308040000")
    block("terminate", 0xcc, "488b0333d2488bcbff10488b07488bd3488bcfff5010")
    for name, shift in (("growKeys", 3), ("growStatus", 2)):
        block(name, 0x2a, "4403fa4c8bf1418bd7488b0948c1e2" + f"{shift:02x}" + "488b01")
        block(name, 0x108, "488918b00144893e")
    block("growRecords", 0x14, "8b5114488bd98beab901000000d1ed03ea4c8b530885d28b73100f44e9488b0b03ea8bc5486bd068")
    block("growRecords", 0x15b, "48897b08b001896b14")

    layout = contract["layout"]
    expected_layout = dict(recordStrideBytes=104, vectorAllocatorOffset=0, vectorPointerOffset=8, vectorCountOffset=16, vectorCapacityOffset=20,
        recordAllocatorOffset=72, recordIdentityPointerOffset=80, recordValuePointerOffset=88, recordCapacityOffset=96,
        durationOffset=56, remainingOffset=60, capturedCountOffset=64, contextKeyEffectOffset=1056, auxiliaryFlagEffectOffset=1004,
        listFlagEffectOffset=1005, listCapacityEffectOffset=1008, primaryScratchEffectOffset=1016, secondaryScratchEffectOffset=1024,
        optionalScratchEffectOffset=1032, roundedChannelsEffectOffset=1000, activeEffectOffset=1040, viewEffectOffset=1048)
    equal("layout", expected_layout, layout)
    equal("sharedStride", shared["recordStrideBytes"], layout["recordStrideBytes"])
    equal("callbackRegistration", dict(offsetFromRegistration=48, method="globalCallback"), contract["registrationCallback"])
    registration = parent["registrationWitnesses"][consumer_contract["classId"]]
    equal("callbackRegistrationJoin", image_base + resolved["globalCallback"],
          struct.unpack("<Q", read(int(registration["registrationRva"], 16) + 48, 8))[0])
    equal("vtableSlots", dict(trigger=16, status=64, terminate=8), contract["vtableSlots"])
    for name, slot in contract["vtableSlots"].items():
        equal("vtableJoin:" + name, image_base + resolved[name],
              struct.unpack("<Q", read(int(consumer_contract["effectVtableRva"], 16) + slot, 8))[0])
    equal("machine", dict(key="retained context pointer equality", initialDuration=512,
        configuredDuration="nextPowerOfTwo(uint32(trunc(float32(uint32(sampleRate)*float32(0.05)))))",
        durationDomain="positive ordinary sample rates whose scaled truncation lies in [1,2^31]",
        trigger="uint32(currentAnonymousCounter-previousCounter)==1 copies duration into remaining",
        refresh="same unit difference preserves shared/local histories; every other difference clears remaining and histories",
        execute="after shared processing, store the current anonymous counter into the parallel status row",
        sameKeyPrepare="reuse record, configure duration, clear remaining and previous counter; prior captured storage/count can persist",
        captureCountOnDiscontinuity="retained while identity/value storage is zeroed",
        keyGrowth="oldCapacity + (oldCapacity + floor(oldCapacity/2) if oldCapacity else 1)",
        statusGrowth="oldCapacity + (oldCapacity + floor(oldCapacity/2) if oldCapacity else 1)",
        recordGrowth="2*oldCapacity + floor(oldCapacity/2) if oldCapacity else 1"), contract["stateMachine"])
    ownership = contract["ownership"]
    equal("allocationSizes", ("roundUpToFour(channels)*256*4", "2 plus 1 when either optional flag is nonzero", "capacity*8", "capacity*4"),
          tuple(ownership[k] for k in ("primaryScratchBytes", "scratchCount", "identitiesBytes", "valuesBytes")))
    equal("allocatorSlots", dict(allocate=8, free=16, reallocate=32), ownership["allocatorSlots"])
    equal("cleanupCaveat", "a record with null value pointer is skipped even when its identity pointer is nonnull", ownership["cleanupCaveat"])
    equal("failureWrites", ("store null value pointer, free newly allocated identity pointer, clear identity pointer, return 2",
          "overwrite identity pointer with null, retain value pointer, return 2",
          "overwrite value pointer with null, free resized identity pointer, clear identity pointer, return 2", True),
          tuple(ownership[k] for k in ("initialValueAllocationFailure", "identityReallocationFailure", "valueReallocationFailure", "capacityWrittenBeforeReallocation")))
    # Reuse the owning descriptor proof, including its numeric mask dispatcher.
    # This caller join adds no second mapping table or native-method catalog.
    from scripts.webui.audio.semantics.wwise_mastering_gain import _descriptor_admission
    descriptor=_descriptor_admission(descriptor_contract['descriptorAdmission'],consumer_contract,read,equal)
    equal('callerDescriptorChannels',[1,12],descriptor['logicalChannels'])
    equal('callerDescriptorStride',True,descriptor['strideAtLeastRoundedChannels'])
    caller=contract['localCaller'];equal('localCallerMethodSet',{'sync','engineControl'},set(caller['consumerMethods']))
    for name in caller['consumerMethods']:
        row=consumer_contract['methods'][name];raw=read(int(row['rva'],16),row['bodyLength'])
        equal('callerMethodLength:'+name,row['bodyLength'],len(raw))
        equal('callerMethodHash:'+name,row['bodySha256'],hashlib.sha256(raw).hexdigest());bodies[name]=raw
    caller_grammar=dict(channelAdmission=('prepare','0fb6c183f80c7641'),
        alignedScratch=('prepare','83c00383e0fc4889b424980400004889bc24a004000041b9090300008983e8030000c1e00a8bf8c783e403000004000000'),
        syncCountAndStride=('sync','8b83e00300004c8d83700200004883bb18040000008bd0440fb6c8488b43180f95c148894424588b83e8030000897c2450884c244833c9c1ea0c8954244033d28944243844894c24304c8b4b28c74424280000000048c744242000000000'),
        controlLogicalCount=('engineControl','8bbd8000000083ff0c0f8745050000'),
        controlDescriptor=('engineControl','44897580488d5424704c8b7568458bc489758444887d884c8bbda8000000498d762841c1e810488bce897c247c4d8bcfc744247480bb0000c744247000010000c74424780c000000'),
        refreshPrimaryAlignment=('refresh','f6421003498be94d8bf04c8bfa4c8be10f8591040000'),
        refreshFormatMatch=('refresh','8b4208448b89e0030000418bd133d084d20f857a040000418bc933c8f7c1000f00000f85690400004433c841f7c100f0ffff0f8559040000'),
        refreshLogicalCount=('refresh','418b8424e00300000fb7f7450fb76f100fb6c8c1e80c894c2460898424f8000000'),
        refreshChunkCapacity=('refresh','b800010000'),
        refreshChunk=('refresh','458bf5442bf34c8bcd443bf0498bd7498bcc440f47f04489742428895c2420'),
        refreshStride=('refresh','418b8424e8030000894424388b44246089442430498d44243044897424284889442420'),
        refreshChunkAdvance=('refresh','b8000100006603f00fb7de413bdd0f8229ffffff'))
    equal('localCallerControls',set(caller_grammar),set(caller['controls']))
    for role,(name,encoded) in caller_grammar.items():
        row=caller['controls'][role];at=row['offset'];raw=bytes.fromhex(encoded)
        equal('callerControlMethod:'+role,name,row['method'])
        equal('callerControl:'+role,raw,bodies[name][at:at+len(raw)],at)
    for role,(name,target) in dict(syncToControl=('sync','engineControl'),controlToInit=('engineControl','engineInit'),refreshToControl=('refresh','engineControl')).items():
        row=caller['calls'][role];at=row['offset'];raw=bodies[name][at:at+5]
        equal('callerCallMethod:'+role,name,row['method']);equal('callerCallOpcode:'+role,b'\xe8',raw[:1],at)
        destination=int(consumer_contract['methods'][name]['rva'],16)+at+5+struct.unpack_from('<i',raw,1)[0]
        equal('callerCallJoin:'+role,int(consumer_contract['methods'][target]['rva'],16),destination,at)
    equal('localCallerLayout',dict(localSampleRate=48000,frameCapacity=256,primaryFrameQuantum=4,logicalChannels=[1,12],normalStride=[4,12],
        normalScratchRequestBytes=[4096,12288],normalStrideFormula='roundUpToFour(logicalChannels)',
        refreshFormatBoundary='all channel-format word bits must match the prepared format',
        frameTraversalBoundary='completing chunk loop terminates for uint16 maxima at most 65280; higher maxima wrap its 16-bit offset'),caller['layout'])
    storage = contract['localStorage']; at = storage['controlCallOffset']
    raw = bodies['engineControl'][at:at + 5]
    equal('storageControlCallOpcode', b'\xe8', raw[:1], at)
    destination = int(consumer_contract['methods']['engineControl']['rva'], 16) + at + 5 + struct.unpack_from('<i', raw, 1)[0]
    equal('storageControlCallJoin', resolved['bufferSetup'], destination, at)
    block('engineControl', 0xa9, '440fb6bd980000004c8d45a00f104df0448bb588000000488b95a8000000'
          '488b4d680f1145ac897da00f104500448975a48975a80f1145cc44887ddc0f114dbc')
    block('engineControl', 0xee, '85c0740ab805008080e9cf040000')
    equal('storageExtent', 334, len(bodies['bufferSetup']))
    # Every non-relative instruction in this complete body is independently
    # recognized. Relative address and format-helper joins were checked above.
    for at, encoded in (
        (0, '48895c241048896c2418488974242041564883ec204883792000498be84c8bf2488bd97530'
            '418b500441b99a000000498b06'),
        (0x39, 'c1e20a498bceff5008488943204885c0750ab80a008080e9e30000008b750448897c243033ff'
               'c1e60a48393b751b498b06'),
        (0x71, '41b9090100008bd6498bceff500848890348397b08751d498b06'),
        (0x92, '41b90b010000488bd6498bceff500848894308488b43104885c0751d498b06'),
        (0xb8, '41b90d010000488bd6498bceff500848894310be0a00808048393b740b48397b0874054885c0'
               '75028bfe807d3c01752985ff7545498b06'),
        (0xf6, '41b917010000ba00040000498bceff50084885c0488943180f44fe85ff751c488d4b284c8bc5498bd6'),
        (0x124, '85c0750bc6830823000001eb028bc7488b7c2430488b5c2438488b6c2440488b742448'
                '4883c420415ec3')):
        block('bufferSetup', at, encoded)
    equal('storageDeclaration', ('conditional', [32, 0, 8, 16], 24, [154, 265, 267, 269], 279, 4, 10, 32,
          60, 1, 1024, 8968, '0x8080000a', '0x80800005',
          'nonnull main pointer skips allocation without capacity check',
          'enabled optional allocation always overwrites its pointer without freeing the previous pointer',
          'first main failure exits immediately; other three are all attempted before the combined check',
          'returns helper result and retains the previous ready flag', 'sets ready flag to one'),
          tuple(storage[k] for k in ('evidenceBoundary', 'mainPointerOffsets', 'optionalPointerOffset', 'allocationTags',
              'optionalAllocationTag', 'strideDescriptorOffset', 'requestShift', 'requestArithmeticBits', 'optionalFlagOffset',
              'optionalFlagValue', 'optionalRequestBytes', 'readyFlagOffset', 'allocationFailure', 'callerFailure', 'reuse',
              'optionalReuse', 'mainFailure', 'formatFailure', 'success')))
    return dict(status="validated", evidenceBoundary="conditional", contextProducerJoined=True, triggerJoined=True,
                recordStrideBytes=104, contextKey="retained context pointer equality", anonymousCounterMeaningProven=False,
                configuredDuration="power-of-two ceiling of truncated float32 sampleRate*0.05",
                resetTrigger="unit difference modulo 2^32", discontinuityClearsHistories=True,
                capturedCountRetainedOnDiscontinuity=True, sameKeySetupReusesRecord=True,
                sharedRecordsSurviveLocalTermination=True, globalCleanupJoined=True,
                executeCriticalSectionDeclarationsJoined=True, liveImportBindingObserved=False,
                nullValuePointerSkipsIdentityCleanup=True, fullAllocatorFailureRecoveryProven=False,
                nullReallocationOverwritesStoredPointer=True, capacityWrittenBeforeReallocation=True,
                normalLocalDspCallerJoined=True,normalLocalDspSampleRate=48000,normalFrameCapacity=256,
                normalLogicalChannels=[1,12],normalStrideRange=[4,12],normalStrideEqualsRoundedChannels=True,
                normalScratchRequestBytes=[4096,12288],refreshRejectsChangedChannelFormat=True,
                completeLocalBufferSetupProven=True, localMainBuffersReusedWithoutCapacityCheck=True,
                localOptionalBufferOverwrittenOnEveryEnabledSetup=True,
                localAllocationFailuresRetainEarlierPointers=True, localBufferCapacityOrRetryRecoveryProven=False,
                frameTraversalOffsetBits=16,maximumFiniteFrameTraversal=65280,fullPrimaryFrameAdmissionProven=False,
                primaryFrameAlignmentProven=True,primaryFrameQuantum=4,largestAlignedPrimaryMaximum=65532,
                generalDescriptorStrideUpperBoundProven=False,actualAllocationCapacityOrLifetimeProven=False,
                completeConcurrentLifetimeProven=False, callbackSchedulingProven=False, runtimeInvocationObserved=False,
                meaningBoundary=contract["meaningBoundary"])


def check_mastering_context_native_inputs(game_root: Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_consumer import load_mastering_consumer_contract, validate_mastering_consumer
    from scripts.webui.audio.semantics.wwise_mastering_updates import load_mastering_contract, validate_mastering_updates
    from scripts.webui.audio.semantics.wwise_mastering_shared import load_mastering_shared_contract, validate_mastering_shared
    from scripts.webui.audio.semantics.wwise_mastering_gain import load_mastering_gain_contract

    def validate(parent, base, read):
        c = load_mastering_consumer_contract(); class_id = c["classId"]
        updates = validate_mastering_updates(load_mastering_contract(), parent["nativeInputs"],
            parent["registrationWitnesses"][class_id], base, read, structural=parent["structuralSchemas"][class_id])
        consumer = validate_mastering_consumer(c, parent, updates, base, read)
        shared = validate_mastering_shared(load_mastering_shared_contract(), parent["nativeInputs"], c, consumer, read)
        return validate_mastering_context(load_mastering_context_contract(), parent, c, consumer, shared, base, read,load_mastering_gain_contract())

    return check_effect_native_extension(game_root, evidence_key="context", validate=validate)
