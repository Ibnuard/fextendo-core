#include <cassert>
#include <cstdint>
#include <cstdio>
using u32=uint32_t;using u64=uint64_t;
#include "/home/blekjek/fextendo-ams195-v13/atmosphere-final/libraries/libvapours/include/vapours/svc/svc_fextendo_memory.hpp"
#include "/home/blekjek/fextendo-ams195-v13/atmosphere-final/libraries/libvapours/include/vapours/svc/svc_memory_map.hpp"
namespace ams::svc {
enum CreateProcessFlag : u32 {
        /* Is 64 bit? */
        CreateProcessFlag_Is64Bit       = (1 << 0),

        /* What kind of address space? */
        CreateProcessFlag_AddressSpaceShift             = 1,
        CreateProcessFlag_AddressSpaceMask              = (7 << CreateProcessFlag_AddressSpaceShift),
        CreateProcessFlag_AddressSpace32Bit             = (0 << CreateProcessFlag_AddressSpaceShift),
        CreateProcessFlag_AddressSpace64BitDeprecated   = (1 << CreateProcessFlag_AddressSpaceShift),
        CreateProcessFlag_AddressSpace32BitWithoutAlias = (2 << CreateProcessFlag_AddressSpaceShift),
        CreateProcessFlag_AddressSpace64Bit             = (3 << CreateProcessFlag_AddressSpaceShift),

        /* Should JIT debug be done on crash? */
        CreateProcessFlag_EnableDebug   = (1 << 4),

        /* Should ASLR be enabled for the process? */
        CreateProcessFlag_EnableAslr    = (1 << 5),

        /* Is the process an application? */
        CreateProcessFlag_IsApplication = (1 << 6),

        /* 4.x deprecated: Should use secure memory? */
        CreateProcessFlag_DeprecatedUseSecureMemory = (1 << 7),

        /* 5.x+ Pool partition type. */
        CreateProcessFlag_PoolPartitionShift            = 7,
        CreateProcessFlag_PoolPartitionMask             = (0xF << CreateProcessFlag_PoolPartitionShift),
        CreateProcessFlag_PoolPartitionApplication      = (0 << CreateProcessFlag_PoolPartitionShift),
        CreateProcessFlag_PoolPartitionApplet           = (1 << CreateProcessFlag_PoolPartitionShift),
        CreateProcessFlag_PoolPartitionSystem           = (2 << CreateProcessFlag_PoolPartitionShift),
        CreateProcessFlag_PoolPartitionSystemNonSecure  = (3 << CreateProcessFlag_PoolPartitionShift),

        /* 7.x+ Should memory allocation be optimized? This requires IsApplication. */
        CreateProcessFlag_OptimizeMemoryAllocation = (1 << 11),

        /* 11.x+ DisableDeviceAddressSpaceMerge. */
        CreateProcessFlag_DisableDeviceAddressSpaceMerge = (1 << 12),

        /* 18.x EnableAliasRegionExtraSize. */
        CreateProcessFlag_EnableAliasRegionExtraSize = (1 << 13),

        /* Private FEXTendo ABI; never an NPDM flag. */
        CreateProcessFlag_FextendoLowWindow = fextendo::RequestFlag,

        /* Mask of all flags. */
        CreateProcessFlag_All = CreateProcessFlag_Is64Bit                        |
                                CreateProcessFlag_AddressSpaceMask               |
                                CreateProcessFlag_EnableDebug                    |
                                CreateProcessFlag_EnableAslr                     |
                                CreateProcessFlag_IsApplication                  |
                                CreateProcessFlag_PoolPartitionMask              |
                                CreateProcessFlag_OptimizeMemoryAllocation       |
                                CreateProcessFlag_DisableDeviceAddressSpaceMerge |
                                CreateProcessFlag_EnableAliasRegionExtraSize |
                                CreateProcessFlag_FextendoLowWindow,
    };
int ResultInvalidCombination(){return 1;} int ResultInvalidAddress(){return 2;} int ResultInvalidEnumValue(){return 3;}
}
namespace svc=ams::svc;
#define AMS_UNREACHABLE_DEFAULT_CASE() default: assert(false)
#define R_UNLESS(c,r) do{if(!(c))return r;}while(0)
struct Param {u32 flags;u64 code_address=0;};
int validate(Param params) {
 R_UNLESS((params.flags & ~ams::svc::CreateProcessFlag_All) == 0, svc::ResultInvalidEnumValue());
 if (ams::svc::fextendo::Requested(params.flags)) {
                R_UNLESS(ams::svc::fextendo::CompatibleFlags(params.flags), svc::ResultInvalidCombination());
                R_UNLESS(params.code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
            }
 return 0;
}
u64 aslr(u32 flags) {
 Param p{flags};auto* out_param=&p;u64 aslr_start=0,aslr_size=0;
 switch (out_param->flags & svc::CreateProcessFlag_AddressSpaceMask) {
                    case svc::CreateProcessFlag_AddressSpace32Bit:
                    case svc::CreateProcessFlag_AddressSpace32BitWithoutAlias:
                        aslr_start = svc::AddressSmallMap32Start;
                        aslr_size  = svc::AddressSmallMap32Size;
                        break;
                    case svc::CreateProcessFlag_AddressSpace64BitDeprecated:
                        aslr_start = svc::AddressSmallMap36Start;
                        aslr_size  = svc::AddressSmallMap36Size;
                        break;
                    case svc::CreateProcessFlag_AddressSpace64Bit:
                        aslr_start = svc::AddressMap39Start;
                        aslr_size  = svc::AddressMap39Size;
                        if (svc::fextendo::Requested(out_param->flags)) {
                            aslr_start = svc::fextendo::NativeStart;
                            aslr_size  = svc::AddressMap39End - aslr_start;
                        }
                        break;
                    AMS_UNREACHABLE_DEFAULT_CASE();
                }
 assert(aslr_size>0);return aslr_start;
}
int page(u32 flags,unsigned m_address_space_width,u64 code_address,u64& m_code_region_start,u64& m_alias_code_region_start) {
 if (ams::svc::fextendo::Requested(flags)) {
                R_UNLESS(m_address_space_width == 39 && ams::svc::fextendo::CompatibleFlags(flags), svc::ResultInvalidCombination());
                R_UNLESS(code_address >= ams::svc::fextendo::NativeStart, svc::ResultInvalidAddress());
                m_code_region_start       = ams::svc::fextendo::NativeStart;
                m_alias_code_region_start = ams::svc::AddressSmallMap32Start;
            }
 return 0;
}
int main(){
 assert(validate({0x40000067,0x100000000})==0);
 assert(validate({0x40000067,0xfffff000})==2);
 assert(validate({0x40000065,0x100000000})==1);
 assert(validate({0x40000063,0x100000000})==1);
 assert(validate({0x40000027,0x100000000})==1);
 assert(validate({0x400000e7,0x100000000})==1);
 assert(validate({0x40002067,0x100000000})==1);
 for(unsigned bit=14;bit<32;bit++)if(bit!=30)assert(validate({0x40000067|(1u<<bit),0x100000000})==3);
 assert(aslr(0x61)==svc::AddressSmallMap32Start);
 assert(aslr(0x65)==svc::AddressSmallMap32Start);
 assert(aslr(0x63)==svc::AddressSmallMap36Start);
 assert(aslr(0x67)==svc::AddressMap39Start);
 assert(aslr(0x40000067)==0x100000000);
 u64 code=99,alias=77;
 assert(page(0x67,39,0x100000000,code,alias)==0&&code==99&&alias==77);
 assert(page(0x40000067,36,0x100000000,code,alias)==1&&code==99&&alias==77);
 assert(page(0x40000067,39,0xfffff000,code,alias)==2&&code==99&&alias==77);
 assert(page(0x40002067,39,0x100000000,code,alias)==1);
 assert(page(0x400000e7,39,0x100000000,code,alias)==1);
 assert(page(0x40000067,39,0x100000000,code,alias)==0&&code==0x100000000&&alias==svc::AddressSmallMap32Start);
 puts("PASS: 1.9.5 upstream 32/36/39 ASLR, opt-in native placement, invalid flags/pools/layout rejection, low-code rejection, unchanged unmarked layouts");
}
