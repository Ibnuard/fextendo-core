#include <cassert>
#include <cstdint>
#include <cstdio>
using u32=uint32_t;using u64=uint64_t;
#include "/home/blekjek/fextendo-ams112-v12/atmosphere-final/libraries/libvapours/include/vapours/svc/svc_fextendo_memory.hpp"
#include "/home/blekjek/fextendo-ams112-v12/atmosphere-final/libraries/libvapours/include/vapours/svc/svc_memory_map.hpp"
namespace ams::svc {
enum CreateProcessParameterFlag : u32 {
        /* Is 64 bit? */
        CreateProcessParameterFlag_64Bit                          = (1 << 0),

        /* What kind of address space? */
        CreateProcessParameterFlag_AddressSpaceShift              = 1,
        CreateProcessParameterFlag_AddressSpaceMask               = (7 << CreateProcessParameterFlag_AddressSpaceShift), /* Should be 15 but Nintendo didn't make 64K usable yet */
        CreateProcessParameterFlag_AddressSpace32Bit              = (0 << CreateProcessParameterFlag_AddressSpaceShift),
        CreateProcessParameterFlag_AddressSpace64Bit36            = (1 << CreateProcessParameterFlag_AddressSpaceShift),
        CreateProcessParameterFlag_AddressSpace32BitNoReserved    = (2 << CreateProcessParameterFlag_AddressSpaceShift),
        CreateProcessParameterFlag_AddressSpace64Bit39            = (3 << CreateProcessParameterFlag_AddressSpaceShift),
        CreateProcessParameterFlag_AddressSpace64Bit42            = (4 << CreateProcessParameterFlag_AddressSpaceShift),

        /* Should JIT debug be done on crash? */
        CreateProcessParameterFlag_EnableJitDebug                 = (1 << 4),

        /* Should ASLR be enabled for the process? */
        CreateProcessParameterFlag_EnableAslr                     = (1 << 5),

        /* Is the process an application? */
        CreateProcessParameterFlag_IsApplication                  = (1 << 6),

        /* 4.x deprecated: Should use secure memory? */
        CreateProcessParameterFlag_DeprecatedUseSecureMemory      = (1 << 7),

        /* 5.x+ Pool partition type. */
        CreateProcessParameterFlag_PoolPartitionShift             = 7,
        CreateProcessParameterFlag_PoolPartitionMask              = (0xF << CreateProcessParameterFlag_PoolPartitionShift),
        CreateProcessParameterFlag_PoolPartitionApplication       = (0 << CreateProcessParameterFlag_PoolPartitionShift),
        CreateProcessParameterFlag_PoolPartitionApplet            = (1 << CreateProcessParameterFlag_PoolPartitionShift),
        CreateProcessParameterFlag_PoolPartitionSystem            = (2 << CreateProcessParameterFlag_PoolPartitionShift),
        CreateProcessParameterFlag_PoolPartitionSystemNonSecure   = (3 << CreateProcessParameterFlag_PoolPartitionShift),

        /* 7.x+ Should memory allocation be optimized? This requires IsApplication. */
        CreateProcessParameterFlag_OptimizeMemoryAllocation       = (1 << 11),

        /* 11.x+ DisableDeviceAddressSpaceMerge. */
        CreateProcessParameterFlag_DisableDeviceAddressSpaceMerge = (1 << 12),

        /* 18.x EnableAddressSanitizer. */
        CreateProcessParameterFlag_EnableAddressSanitizer         = (1 << 13),

        /* 23.x EnableShadowStack. */
        CreateProcessParameterFlag_EnableShadowStack              = (1 << 17),

        /* Private FEXTendo ABI; never an NPDM flag. */
        CreateProcessParameterFlag_FextendoLowWindow = fextendo::RequestFlag,

        /* Mask of all flags. */
        CreateProcessParameterFlag_All = CreateProcessParameterFlag_64Bit                 |
                                CreateProcessParameterFlag_AddressSpaceMask               |
                                CreateProcessParameterFlag_EnableJitDebug                 |
                                CreateProcessParameterFlag_EnableAslr                     |
                                CreateProcessParameterFlag_IsApplication                  |
                                CreateProcessParameterFlag_PoolPartitionMask              |
                                CreateProcessParameterFlag_OptimizeMemoryAllocation       |
                                CreateProcessParameterFlag_DisableDeviceAddressSpaceMerge |
                                CreateProcessParameterFlag_EnableAddressSanitizer         |
                                CreateProcessParameterFlag_EnableShadowStack |
                                CreateProcessParameterFlag_FextendoLowWindow,
    };
int ResultInvalidCombination(){return 1;} int ResultInvalidAddress(){return 2;} int ResultInvalidEnumValue(){return 3;}
}
namespace svc=ams::svc;
#define AMS_UNREACHABLE_DEFAULT_CASE() default: assert(false)
#define R_UNLESS(c,r) do{if(!(c))return r;}while(0)
struct Param {u32 flags;u64 code_address=0;};
int validate(Param params) {
 R_UNLESS((params.flags & ~ams::svc::CreateProcessParameterFlag_All) == 0, svc::ResultInvalidEnumValue());
 if (ams::svc::fextendo::Requested(params.flags)) {
                R_UNLESS(ams::svc::fextendo::CompatibleFlags(params.flags), svc::ResultInvalidCombination());
                R_UNLESS(params.code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
            }
 return 0;
}
u64 aslr(u32 flags) {
 Param p{flags};auto* out_param=&p;u64 aslr_start=0,aslr_size=0;
 switch (out_param->flags & svc::CreateProcessParameterFlag_AddressSpaceMask) {
                    case svc::CreateProcessParameterFlag_AddressSpace32Bit:
                    case svc::CreateProcessParameterFlag_AddressSpace32BitNoReserved:
                        aslr_start = svc::AddressSmallMap32Start;
                        aslr_size  = svc::AddressSmallMap32Size;
                        break;
                    case svc::CreateProcessParameterFlag_AddressSpace64Bit36:
                        aslr_start = svc::AddressSmallMap36Start;
                        aslr_size  = svc::AddressSmallMap36Size;
                        break;
                    case svc::CreateProcessParameterFlag_AddressSpace64Bit39:
                        aslr_start = svc::AddressMap39Start;
                        aslr_size  = svc::AddressMap39Size;
                        if (svc::fextendo::Requested(out_param->flags)) {
                            aslr_start = svc::fextendo::NativeStart;
                            aslr_size  = svc::AddressMap39End - aslr_start;
                        }
                        break;
                    case svc::CreateProcessParameterFlag_AddressSpace64Bit42:
                        aslr_start = svc::AddressMap42Start;
                        aslr_size  = svc::AddressMap42Size;
                        break;
                    AMS_UNREACHABLE_DEFAULT_CASE();
                }
 assert(aslr_size>0);return aslr_start;
}
int page(u32 flags, unsigned address_space_width,u64 code_address,u64& m_code_region_start,u64& m_alias_code_region_start) {
 if (ams::svc::fextendo::Requested(flags)) {
                R_UNLESS(address_space_width == 39 && ams::svc::fextendo::CompatibleFlags(flags), svc::ResultInvalidCombination());
                R_UNLESS(code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
                m_code_region_start       = ams::svc::fextendo::NativeStart;
                m_alias_code_region_start = ams::svc::AddressSmallMap32Start;
            }
 return 0;
}
int main(){
 assert(validate({0x40000067,0x100000000})==0);
 assert(validate({0x40020067,0x100000000})==0);
 assert(validate({0x40004067,0x100000000})==3);
 assert(validate({0x40000069,0x100000000})==1);
 assert(validate({0x40000067,0xfffff000})==2);
 assert(validate({0x40000065,0x100000000})==1);
 assert(aslr(0x65)==svc::AddressSmallMap32Start);
 assert(aslr(0x63)==svc::AddressSmallMap36Start);
 assert(aslr(0x67)==svc::AddressMap39Start);
 assert(aslr(0x69)==svc::AddressMap42Start);
 assert(aslr(0x40000067)==0x100000000);
 assert(aslr(0x40020067)==0x100000000);
 u64 code=99,alias=77;
 assert(page(0x67,39,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x69,42,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x40000067,42,0x100000000,code,alias)==1&&code==99&&alias==77);
 assert(page(0x40000067,39,0xfffff000,code,alias)==2&&code==99&&alias==77);
 assert(page(0x40002067,39,0x100000000,code,alias)==1);
 assert(page(0x400000e7,39,0x100000000,code,alias)==1);
 assert(page(0x40000067,39,0x100000000,code,alias)==0&&code==0x100000000&&alias==svc::AddressSmallMap32Start);
 puts("PASS: upstream 32/36/39/42 ASLR selection, opt-in high native placement, ShadowStack flag, low-code rejection, non-application and ASan rejection, unchanged unmarked layouts");
}
