"""Decode converter header negotiation and revision routing below its controls.

Source length checks are nominal schema checks. A recognized destination keeps
its existing length word, so these routes do not establish writable capacity.
"""
from __future__ import annotations

import hashlib
import json
import struct
from functools import lru_cache
from pathlib import Path

from scripts.game_data.contracts import CONTRACTS_DIR
from scripts.webui.audio.semantics.wwise_effect_updates import EffectUpdateError


@lru_cache(maxsize=1)
def load_mastering_revisions_contract():
    return json.loads((CONTRACTS_DIR / "wwise_mastering_revisions_native.json").read_text(encoding="utf-8"))


def _header_program(body, row, source_version, source_size, target_version, target_size):
    registers = {1:"source", 2:"target", row["sourceRegister"]:"source", row["targetRegister"]:"target"}
    headers = dict(source={0:source_version,4:source_size}, target={0:target_version,4:target_size})
    at = row["headerStart"]; phase = "header"; comparison = None; visited = set()
    def take(n):
        nonlocal at
        if at+n > len(body):raise ValueError("truncated header instruction")
        value=body[at:at+n];at+=n;return value
    def operand(rex,modrm):
        mode=modrm>>6;index=(modrm&7)|((rex&1)<<3)
        if mode==3:return "register",index
        if mode not in (0,1) or modrm&7==4:raise ValueError("unmodeled header address")
        displacement=int.from_bytes(take(1),'little',signed=True) if mode==1 else 0
        role=registers.get(index)
        if role not in headers or displacement not in (0,4):raise ValueError("unjoined source/target header field")
        return role,displacement
    def read(location):
        role,index=location;value=registers.get(index) if role=="register" else headers[role][index]
        if type(value) is not int:raise ValueError("undefined integer header operand")
        return value
    def write(location,value):
        role,index=location
        if role=="register":registers[index]=value&0xffffffff
        elif role=="target":headers[role][index]=value&0xffffffff
        else:raise ValueError("unexpected source-header write")
    for _ in range(96):
        if phase=="header" and at==row["headerEnd"]:
            phase="decision";at=row["decisionStart"]
        if phase=="decision" and at in row["decisionEnds"].values():
            return dict(status="route",entryOffset=at,sourceVersion=registers[1],selectedVersion=registers[0],outputHeader=headers["target"])
        if (phase,at) in visited:raise ValueError("header route cycles")
        visited.add((phase,at));begin=at;rex=0
        if 0x40<=body[at]<=0x4f:rex=take(1)[0]&15
        if rex&8:raise ValueError("header operation is not a 32-bit word")
        opcode=take(1)[0]
        if opcode in (0x74,0x75,0x0f):
            if opcode==0x0f:
                opcode=take(1)[0]
                if opcode not in (0x84,0x85):raise ValueError("unsupported header branch")
                width=4;equal=opcode==0x84
            else:width=1;equal=opcode==0x74
            if comparison is None:raise ValueError("header branch without comparison")
            displacement=int.from_bytes(take(width),'little',signed=True)
            if comparison==equal:at+=displacement
            if not 0<=at<len(body):raise ValueError("header branch leaves body")
            continue
        if opcode==0xb8:
            code=int.from_bytes(take(4),'little')
            if code not in (0x80260202,0x80800008):raise ValueError("unrecognized header error")
            return dict(status="error",error=code,outputHeader=headers["target"])
        if opcode==0x3d:comparison=read(("register",0))==int.from_bytes(take(4),'little');continue
        if opcode not in (0x8b,0x89,0x81,0x83,0x3b):raise ValueError(f"unsupported header opcode +{begin:#x}")
        modrm=take(1)[0];register=((modrm>>3)&7)|((rex&4)<<1);location=operand(rex,modrm)
        if opcode==0x8b:write(("register",register),read(location))
        elif opcode==0x89:write(location,read(("register",register)))
        elif opcode==0x3b:comparison=read(("register",register))==read(location)
        else:
            if register!=7:raise ValueError("header immediate is not comparison")
            immediate=int.from_bytes(take(1 if opcode==0x83 else 4),'little',signed=opcode==0x83)&0xffffffff
            comparison=read(location)==immediate
    raise ValueError("header instruction bound exceeded")


def _preserving_bridge(body,start,end):
    """Only stack stores; no instruction here can alter the selected revisions."""
    at=start
    while at<end:
        rex=0
        if 0x40<=body[at]<=0x4f:rex=body[at]&15;at+=1
        if body[at]==0x89 and rex&8:at+=1
        elif body[at:at+2]==b'\x0f\x29':at+=2
        else:raise ValueError("revision bridge contains an unproved operation")
        if at+2>end:raise ValueError("truncated bridge stack store")
        modrm,sib=body[at:at+2];at+=2
        if modrm&7!=4 or sib!=0x24 or rex&1:raise ValueError("bridge store is not relative to RSP")
        mode=modrm>>6
        if mode not in (1,2):raise ValueError("unsupported bridge displacement")
        at+=1 if mode==1 else 4
    if at!=end:raise ValueError("bridge does not end at revision dispatch")


def validate_mastering_revisions(contract,native_inputs,dynamics_contract,dynamics,read):
    def equal(check,expected,actual,offset=0):
        if expected!=actual:raise EffectUpdateError("masteringRevisions",check,offset,expected,actual)
    equal("schema","endfield.wwise-mastering-revisions-native-contract.v1",contract["schema"])
    equal("reviewStatus","reviewed",contract["status"]);equal("boundary","direct",contract["evidenceBoundary"])
    equal("inputs",native_inputs,contract["nativeInputs"]);equal("parentInputs",native_inputs,dynamics_contract["nativeInputs"])
    equal("parentProof","validated",dynamics["status"]);equal("domains",{"bands","peak"},set(contract["domains"]))
    outcomes=[]
    for domain,row in contract["domains"].items():
        method="convertBands" if domain=="bands" else "convertPeak";equal("method",method,row["dynamicsMethod"])
        source=dynamics_contract["methods"][method];body=read(int(source["rva"],16),source["bodyLength"])
        equal("methodHash:"+domain,source["bodySha256"],hashlib.sha256(body).hexdigest())
        equal("headerRegisters",(14,6) if domain=="bands" else (3,7),(row["sourceRegister"],row["targetRegister"]))
        equal("decisionRoles",{"legacyToLegacy","legacyToCurrent","currentToCurrent"},set(row["decisionEnds"]))
        try:_preserving_bridge(body,row["headerEnd"],row["decisionStart"])
        except (ValueError,IndexError) as error:raise EffectUpdateError("masteringRevisions","preservingBridge:"+domain,row["headerEnd"],"stack stores preserve selected/source revisions",str(error)) from error
        low=1 if domain=="bands" else 3;versions={1:0x01010000+low,2:0x01020000+low};sizes={1:116 if domain=="bands" else 32,2:144 if domain=="bands" else 32}
        equal("storedLayouts",{str(k):dict(version=versions[k],nominalBytes=sizes[k]) for k in (1,2)},row["layouts"])
        for revision,version in list(versions.items())+[(0,0),(3,0xffffffff)]:
            for size in sorted({0,32,116,144,0xffffffff,sizes.get(revision,0)}):
                for target in (0,versions[1],versions[2],0xffffffff):
                    for previous_size in (0,7,0xffffffff):
                        try:actual=_header_program(body,row,version,size,target,previous_size)
                        except (ValueError,IndexError) as error:raise EffectUpdateError("masteringRevisions","headerProgram:"+domain,row["headerStart"],"admitted framing/dispatch program",str(error)) from error
                        output={0:target,4:previous_size}
                        if revision not in sizes or size!=sizes.get(revision):expected=dict(status="error",error=0x80260202,outputHeader=output)
                        else:
                            selected=target if target in versions.values() else version
                            if target not in versions.values():output={0:version,4:size}
                            if revision==2 and selected==versions[1]:expected=dict(status="error",error=0x80800008,outputHeader=output)
                            else:
                                role="legacyToLegacy" if selected==versions[1] else "legacyToCurrent" if revision==1 else "currentToCurrent"
                                expected=dict(status="route",entryOffset=row["decisionEnds"][role],sourceVersion=version,selectedVersion=selected,outputHeader=output)
                        equal("headerOutcome:"+domain,expected,actual,row["headerStart"]);outcomes.append((domain,revision,size,target,previous_size))
    equal("lengthMeaning","nominal source size equality; recognized target length retained without validation",contract["lengthMeaning"])
    return dict(status="validated",evidenceBoundary="direct",headerNegotiationAndRevisionRoutingProven=True,
        routes=["legacyToLegacy","legacyToCurrent","currentToCurrent"],currentToLegacyRejected=True,
        recognizedDestinationLengthValidated=False,writableDestinationCapacityProven=False,
        legacyControlArithmeticProven=False,runtimeUseObserved=False,checkedHeaderCases=len(outcomes),meaningBoundary=contract["meaningBoundary"])


def check_mastering_revisions_native_inputs(game_root:Path):
    from scripts.webui.audio.semantics.wwise_effect_native import check_effect_native_extension
    from scripts.webui.audio.semantics.wwise_mastering_dynamics import load_mastering_dynamics_contract,validate_mastering_dynamics_effect_context
    def validate(parent,base,read):
        dynamics=validate_mastering_dynamics_effect_context(parent,base,read)
        return validate_mastering_revisions(load_mastering_revisions_contract(),parent["nativeInputs"],load_mastering_dynamics_contract(),dynamics,read)
    return check_effect_native_extension(game_root,evidence_key="revisions",validate=validate)
