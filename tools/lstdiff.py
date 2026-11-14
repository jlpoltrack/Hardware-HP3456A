"""Explain every byte change between two builds of the same ROM source.

Usage: lstdiff.py old.lst old.bin new.lst new.bin
Pairs listing lines by source text, then checks each changed line is either new/removed
source or an instruction whose only change is an address operand that moved with its target.
"""
import difflib
import re
import sys
from m6800 import decode

LINE = re.compile(r'^([0-9a-f]{4}) : ((?:[0-9a-f]{2})*)\s*(.*)$')


def parse(path):
    out = []
    for l in open(path, errors='replace').read().splitlines():
        m = LINE.match(l)
        if m:
            out.append((int(m.group(1), 16), bytes.fromhex(m.group(2)), m.group(3).strip()))
    return out


old_l, old_b, new_l, new_b = sys.argv[1:5]
old, new = parse(old_l), parse(new_l)
ob, nb = open(old_b, 'rb').read(), open(new_b, 'rb').read()
sm = difflib.SequenceMatcher(None, [x[2] for x in old], [x[2] for x in new], autojunk=False)

amap, pairs, added, removed = {}, [], [], []
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal':
        for k in range(i2 - i1):
            o, n = old[i1 + k], new[j1 + k]
            amap.setdefault(o[0], n[0])
            pairs.append((o, n))
    else:
        removed += [x for x in old[i1:i2] if x[1]]
        added += [x for x in new[j1:j2] if x[1]]

shifts, unexplained, relocated = {}, [], 0
for o, n in pairs:
    if o[1]:
        shifts.setdefault(n[0] - o[0], []).append(o[0])
    if o[1] == n[1]:
        continue
    if len(o[1]) != len(n[1]):
        unexplained.append(('size change (relaxation)', o, n))
        continue
    if o[2].split()[0] == 'dw' and len(o[1]) == 2:
        ov, nv = int.from_bytes(o[1], 'big'), int.from_bytes(n[1], 'big')
        if amap.get(ov) == nv:
            relocated += 1
            continue
    oi, ni = decode(ob, o[0]), decode(nb, n[0])
    if oi[:2] == ni[:2] and amap.get(oi[2]) == ni[2]:
        relocated += 1
        continue
    unexplained.append(('operand not explained by relocation', o, n))

print('Added source bytes:')
for a, b, s in added:
    print(f'  {a:04X}  {b.hex():8} {s}')
print('Removed source bytes:')
for a, b, s in removed:
    print(f'  {a:04X}  {b.hex():8} {s}')
print('Address shift (new - old) by old address range:')
for d, addrs in sorted(shifts.items(), key=lambda kv: min(kv[1])):
    print(f'  {d:+d}: {min(addrs):04X}-{max(addrs):04X} ({len(addrs)} lines)')
print(f'Lines whose bytes changed only by relocated address operands: {relocated}')
print(f'Unexplained changes: {len(unexplained)}')
for why, o, n in unexplained:
    print(f'  {why}: {o[0]:04X} {o[1].hex()} -> {n[0]:04X} {n[1].hex()}  {n[2]}')
