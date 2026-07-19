import asyncio, sys
from ps4debug import PS4Debug

PS4_IP        = None
PS4DEBUG_PORT = 744
TARGET_FW     = None
CURRENT_FW    = None

async def scan_process(ps4, pid, maps, pattern, max_regions=200, max_size=0x10000000):
    found = []
    count = 0
    for m in maps:
        if count >= max_regions:
            break
        try:
            prot = int(m.prot)
        except:
            continue
        size = m.end - m.start
        if size > max_size or size < 0x100 or not (prot & 1):
            continue
        count += 1
        CHUNK = 0x80000
        addr = m.start
        while addr < m.end:
            read_size = min(CHUNK, m.end - addr)
            try:
                data = await ps4.read_memory(pid, addr, read_size)
                idx = 0
                while True:
                    pos = data.find(pattern, idx)
                    if pos < 0:
                        break
                    found.append((addr + pos, data[pos:pos + len(pattern) + 16]))
                    idx = pos + 1
            except:
                pass
            addr += read_size
    return found

async def patch_process(ps4, proc, current_fw, target_fw):
    patches = 0
    try:
        maps = await ps4.get_process_maps(proc.pid)
    except Exception as e:
        print(f"cannot get process maps: {e}")
        return 0

    old_text = f"HEN {current_fw}"
    new_text = f"HEN {target_fw}"
    old_utf16 = old_text.encode("utf-16-le")
    new_utf16 = new_text.encode("utf-16-le")
    results_utf16 = await scan_process(ps4, proc.pid, maps, old_utf16, max_regions=500, max_size=0x1000000)
    
    if results_utf16:
        print(f"'{old_text}' -> {len(results_utf16)} found")
        len_diff = len(new_text) - len(old_text)
        
        for addr, _ in results_utf16:
            try:
                if len_diff == 0:
                    await ps4.write_memory(proc.pid, addr, new_utf16)
                    patches += 1
                else:
                    prefix_addr = addr - 4
                    prefix_bytes = await ps4.read_memory(proc.pid, prefix_addr, 4)
                    old_len = int.from_bytes(prefix_bytes, "little")
                    
                    if old_len == len(old_text):
                        new_len_bytes = len(new_text).to_bytes(4, "little")
                        await ps4.write_memory(proc.pid, prefix_addr, new_len_bytes)
                        await ps4.write_memory(proc.pid, addr, new_utf16)
                        patches += 1
                        print(f"updated at {hex(prefix_addr)} to {len(new_text)}")
            except Exception as e:
                print(f"failed writing at {hex(addr)}: {e}")
    return patches


async def run():
    global CURRENT_FW

    print("connecting to ps4debug")
    try:
        ps4 = PS4Debug(host=PS4_IP, port=PS4DEBUG_PORT, timeout=15.0)
        procs = await ps4.get_processes()
        print(f"connected! {len(procs)} processes")
    except Exception as e:
        print(f"connection failed: {e}")
        return False

    if CURRENT_FW == TARGET_FW:
        print("current and target fw are the same")
        return False

    print(f"\nspoofing: {CURRENT_FW} -> {TARGET_FW}")

    sys_procs = []
    for proc in procs:
        name = proc.name.lower()
        if any(x in name for x in ["sceshellui", "shellui"]):
            sys_procs.append(proc)

    total = 0
    for proc in sys_procs:
        print(f"\n{proc.name} (PID: {proc.pid})")
        p = await patch_process(ps4, proc, CURRENT_FW, TARGET_FW)
        total += p

    print("\n" + "=" * 60)
    if total > 0:
        print(f"done! {total} patch(es*) applied")
        print(f"{CURRENT_FW} -> {TARGET_FW}")
        print()
        print("re-open System Information tab")
        print("patch resets upon rest mode/shutdown/restart")
    else:
        print("no patches applied :(")
    print("=" * 60)
    return total > 0


def main():
    print("shitspoof 0.0: never update edition")
    print("thanks: andrew2007, lucas firmware spoofer for the way text is changed")
    version = input(f"What version are you looking to spoof to? (i.e.: 13.52, 69.69): ").strip()
    if version:
        TARGET_FW = version
    ip = input(f"What's your PS4 IP address? (i.e.: 10.0.0.1, 192.168.0.1?): ").strip()
    if ip:
        PS4_IP = ip
    c_version = input(f"What version are you currently using? (i.e.: 5.05, 6.72, 9.00, 11.00) *THIS INCLUDES ALREADY SPOOFED FW'S, IF YOU SPOOFED TO 13.52, WRITE 13.52* : ").strip()
    if c_version:
        CURRENT_FW = c_version
    
    print(f"IP: {PS4_IP}, Target: {TARGET_FW}, Current: {CURRENT_FW} (If any of these are blank, rerun the script, it won't work)")
    asyncio.run(run())


if __name__ == "__main__":
    main()
