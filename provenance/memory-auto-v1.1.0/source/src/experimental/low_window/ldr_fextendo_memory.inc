/* SPDX-License-Identifier: MIT
 * Included inside ams::ldr's anonymous namespace. Code is already mounted;
 * read the descriptor before ASLR placement or svcCreateProcess.
 */
Result ReadFextendoMemoryDescriptor(bool *present, const char *path, bool automatic) {
    *present = false;
    fs::FileHandle file;
    const Result opened = fs::OpenFile(std::addressof(file), path, fs::OpenMode_Read);
    if (fs::ResultPathNotFound::Includes(opened)) R_SUCCEED();
    R_TRY(opened);
    ON_SCOPE_EXIT { fs::CloseFile(file); };

    s64 size = 0;
    R_TRY(fs::GetFileSize(std::addressof(size), file));
    R_UNLESS(size == svc::fextendo::DescriptorSize, ldr::ResultInvalidMeta());
    unsigned char descriptor[svc::fextendo::DescriptorSize];
    size_t read_size = 0;
    R_TRY(fs::ReadFile(std::addressof(read_size), file, 0, descriptor, sizeof(descriptor)));
    R_UNLESS(automatic ? svc::fextendo::ValidAutomaticDescriptor(descriptor, read_size) :
        svc::fextendo::ValidDescriptor(descriptor, read_size), ldr::ResultInvalidMeta());
    *present = true;
    R_SUCCEED();
}

Result ApplyFextendoMemoryDescriptor(svc::CreateProcessParameter *param) {
    bool legacy, automatic;
    R_TRY(ReadFextendoMemoryDescriptor(std::addressof(legacy),
        ENCODE_ATMOSPHERE_CODE_PATH("/fxtmem"), false));
    R_TRY(ReadFextendoMemoryDescriptor(std::addressof(automatic),
        ENCODE_ATMOSPHERE_CODE_PATH("/fxtauto"), true));
    R_UNLESS(!(legacy && automatic), ldr::ResultInvalidMeta());
    if (automatic) {
        R_UNLESS(svc::fextendo::CompatibleAutomaticFlags(param->flags) &&
            param->system_resource_num_pages == 0, ldr::ResultInvalidMeta());
        /* This runs before DecideAddressSpaceLayout and svcCreateProcess.
         * Keep the NPDM stock-compatible; supply the 39-bit resource pool here. */
        param->flags = svc::fextendo::PromotedFlags(param->flags);
        param->system_resource_num_pages = svc::fextendo::AutomaticSystemResourcePages;
    } else if (legacy) {
        R_UNLESS(svc::fextendo::CompatibleFlags(param->flags), ldr::ResultInvalidMeta());
        param->flags |= svc::CreateProcessFlag_FextendoLowWindow;
    }
    R_SUCCEED();
}
