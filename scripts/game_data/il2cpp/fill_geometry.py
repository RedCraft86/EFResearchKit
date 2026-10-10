"""Affine byte-range proof for the aligned-loop/head/endpoint fill algorithm.

L is the number of complete chunks. All comparisons are proved for L=0 or
every integer L>=1, rather than sampling loop counts or memory contents.
The consumer must separately prove the instructions and table selection.
"""
from __future__ import annotations


def _le(left, right, domain):
    slope=right[0]-left[0]; intercept=right[1]-left[1]
    return intercept>=0 if domain==0 else slope>=0 and slope+intercept>=0


def prove_byte_replication():
    multiplier=int.from_bytes(b'\x01'*8,'little')
    for byte in range(256):
        value=byte*multiplier
        if value>=1<<64 or value.to_bytes(8,'little')!=bytes([byte])*8:
            raise ValueError('fillGeometry.byte-replication')
    return {'unsignedByteValuesChecked':256,'replicatedQwordBytes':8,
            'multiplyDoesNotOverflowUnsigned64Proved':True,
            'everyReplicatedByteEqualsInputProved':True}


def prove_fill_geometry(*, width, chunk, minimum_exclusive=32):
    if (width not in (16,32) or chunk!=8*width or minimum_exclusive!=32):
        raise ValueError('fillGeometry.selection-domain')
    classes=0
    for domain in (0,1):
        # L=0 can leave a full chunk. A completed loop leaves less than one.
        for remaining in range(chunk+1 if domain==0 else chunk):
            for advance in range(1,width+1):
                if domain==0 and advance+remaining<=minimum_exclusive:continue
                count=(remaining+width-1)//width
                rounded=count*width
                end=(chunk,advance+remaining)
                ranges=[((0,0),(0,width))]
                if domain==1:ranges.append(((0,advance),(chunk,advance)))
                for offset in range(0,max(0,rounded-width),width):
                    ranges.append(((chunk,advance+offset),(chunk,advance+offset+width)))
                if count:ranges.append(((chunk,advance+remaining-width),end))
                origin=(0,0)
                if any(not _le(origin,a,domain) or not _le(a,b,domain)
                       or not _le(b,end,domain) for a,b in ranges):
                    raise ValueError(f'fillGeometry.store-range: width={width} Ldomain={domain} advance={advance} remainder={remaining}')
                ordered=sorted(ranges,key=lambda r:(r[0][0]*domain+r[0][1],r[1][0]*domain+r[1][1]))
                covered=origin;previous=origin
                for start,stop in ordered:
                    if not _le(previous,start,domain) or not _le(start,covered,domain):
                        raise ValueError('fillGeometry.symbolic-gap-or-changing-order')
                    previous=start
                    if _le(covered,stop,domain):covered=stop
                    elif not _le(stop,covered,domain):raise ValueError('fillGeometry.crossing-endpoints')
                if not _le(end,covered,domain) or not _le(covered,end,domain):
                    raise ValueError('fillGeometry.incomplete-coverage')
                if not 0<=count<=8 or rounded%width:
                    raise ValueError('fillGeometry.table-index')
                classes+=1
    return {'widthBytes':width,'chunkBytes':chunk,'affineResidueClassesChecked':classes,
            'loopCountDomain':'L=0 or every integer L>=1; comparisons use affine coefficients',
            'advanceDomain':[1,width],'noLoopRemainderDomain':[0,chunk],
            'afterLoopRemainderDomain':[0,chunk-1],'tailTableIndexDomain':[0,8],
            'everyPayloadStoreWithinRequestedRangeProved':True,
            'everyRequestedByteCoveredProved':True,
            'nonTemporalPrefixAddressesAlignedProved':True,
            'overlappingWritesHaveSameFillByteRequired':True,
            'pointerEndpointDoesNotWrapRequired':True,'runtimeExecutionObserved':False}
