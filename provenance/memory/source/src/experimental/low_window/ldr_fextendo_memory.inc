/* SPDX-License-Identifier: MIT
 * Included inside ams::ldr's anonymous namespace. Code is already mounted;
 * read the descriptor before ASLR placement or svcCreateProcess.
 */
Result ApplyFextendoMemoryDescriptor(svc::CreateProcessParameter *param) {
    fs::FileHandle file;
    const Result opened = fs::OpenFile(std::addressof(file),
        ENCODE_ATMOSPHERE_CODE_PATH("/fxtmem"), fs::OpenMode_Read);
    if (fs::ResultPathNotFound::Includes(opened)) R_SUCCEED();
    R_TRY(opened);
    ON_SCOPE_EXIT { fs::CloseFile(file); };

    s64 size = 0;
    R_TRY(fs::GetFileSize(std::addressof(size), file));
    R_UNLESS(size == svc::fextendo::DescriptorSize, ldr::ResultInvalidMeta());
    unsigned char descriptor[svc::fextendo::DescriptorSize];
    size_t read_size = 0;
    R_TRY(fs::ReadFile(std::addressof(read_size), file, 0, descriptor, sizeof(descriptor)));
    R_UNLESS(svc::fextendo::ValidDescriptor(descriptor, read_size), ldr::ResultInvalidMeta());
    R_UNLESS(svc::fextendo::CompatibleFlags(param->flags), ldr::ResultInvalidMeta());
    param->flags |= svc::CreateProcessFlag_FextendoLowWindow;
    R_SUCCEED();
}
