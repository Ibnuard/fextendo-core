/* SPDX-License-Identifier: LGPL-2.1-or-later
 * One hbloader for stock 32-bit no-alias and FEXTendo 39-bit low-window.
 * The loader has already selected the process layout. Never infer it from SD.
 * Caller holds the virtmem lock. Reservation storage uses the private BSS heap.
 */
static VirtmemReservation *fxt_guest_reservation;
static int fxt_process_mode(void) {
    u64 base = 0, size = 0, alias = 0;
    if (R_FAILED(svcGetInfo(&base, InfoType_AslrRegionAddress, CUR_PROCESS_HANDLE, 0)) ||
        R_FAILED(svcGetInfo(&size, InfoType_AslrRegionSize, CUR_PROCESS_HANDLE, 0)) ||
        R_FAILED(svcGetInfo(&alias, InfoType_AliasRegionSize, CUR_PROCESS_HANDLE, 0))) return 0;
    if (base == UINT64_C(0x200000) && size == UINT64_C(0x7fffe00000)) return 39;
    if (base < UINT64_C(0x100000000) && size == UINT64_C(0x100000000) - base && !alias) return 32;
    return 0;
}
static u64 fxt_limit_heap(u64 wanted) {
    u64 limit = 0;
    if (!fxt_process_mode() ||
        R_FAILED(svcGetInfo(&limit, InfoType_HeapRegionSize, CUR_PROCESS_HANDLE, 0))) return 0;
    limit &= ~UINT64_C(0x1fffff);
    return wanted < limit ? wanted : limit;
}
static void *fxt_find_native(size_t size) {
    const int mode = fxt_process_mode();
    if (!mode || !size) return NULL;
    if (mode == 39 && !fxt_guest_reservation)
        fxt_guest_reservation = virtmemAddReservation((void *)UINT64_C(0x200000), UINT64_C(0xffe00000));
    if (mode == 39 && !fxt_guest_reservation) return NULL;
    void *address = virtmemFindCodeMemory(size, 0);
    uintptr_t at = (uintptr_t)address;
    const u64 end = mode == 39 ? UINT64_C(0x8000000000) : UINT64_C(0x100000000);
    const u64 floor = mode == 39 ? UINT64_C(0x100000000) : UINT64_C(0x200000);
    if (at < floor || at >= end || size > end - at) return NULL;
    return address;
}
