/* Execute the production descriptor reader and hbloader allocator with only
 * filesystem/kernel calls substituted. No Switch/device claim. */
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <memory>
#include <string>
#include <map>
#include <vector>
#include <limits>
#include "../src/experimental/low_window/fextendo_memory_abi.hpp"
using Result=int;using s64=int64_t;using u64=uint64_t;
template<class F> struct Guard { F f;~Guard(){f();} };
struct Defer { template<class F> auto operator+(F f){return Guard<F>{f};} };
#define ON_SCOPE_EXIT auto closer=Defer{}+[&]()
#define R_SUCCEED() return 0
#define R_TRY(x) do{const int r=(x);if(r)return r;}while(0)
#define R_UNLESS(c,r) do{if(!(c))return (r);}while(0)
#define R_FAILED(r) ((r)!=0)
#define ENCODE_ATMOSPHERE_CODE_PATH(p) p
namespace ams::svc {
constexpr uint32_t CreateProcessFlag_FextendoLowWindow=fextendo::RequestFlag;
struct CreateProcessParameter { uint32_t flags;uint32_t system_resource_num_pages;uint64_t code_address=0xfeed; };
}
namespace svc=ams::svc;
namespace ldr {int ResultInvalidMeta(){return 2;}}
namespace fs {
using FileHandle=std::string;constexpr int OpenMode_Read=1;
struct ResultPathNotFound {static bool Includes(Result r){return r==1;}};
std::map<std::string,std::vector<unsigned char>> files;
int opened,closed,error,short_read;
Result OpenFile(FileHandle *out,const char *path,int){if(error==1)return 99;if(!files.count(path))return 1;*out=path;opened++;return 0;}
void CloseFile(FileHandle){closed++;}
Result GetFileSize(s64 *n,FileHandle f){if(error==2)return 99;*n=files.at(f).size();return 0;}
Result ReadFile(size_t *n,FileHandle f,int,void *out,size_t size){if(error==3)return 99;*n=size-short_read;memcpy(out,files.at(f).data(),*n);return 0;}
}
#include "../src/experimental/low_window/ldr_fextendo_memory.inc"
struct VirtmemReservation{};static VirtmemReservation reservation;
enum {InfoType_AslrRegionAddress,InfoType_AslrRegionSize,InfoType_AliasRegionSize,InfoType_HeapRegionSize};
constexpr int CUR_PROCESS_HANDLE=0;
u64 info[4];int query_error,reservations,finds,reserve_fail;uintptr_t candidate;
Result svcGetInfo(u64 *out,int id,int,int){if(query_error)return 1;*out=info[id];return 0;}
VirtmemReservation *virtmemAddReservation(void *p,size_t n){assert((uintptr_t)p==0x200000&&n==0xffe00000);reservations++;return reserve_fail?nullptr:&reservation;}
void *virtmemFindCodeMemory(size_t,int){finds++;return (void*)candidate;}
#include "../src/experimental/low_window/forwarder_auto.inc"

int main(){
    const std::vector<unsigned char> automatic={'F','X','T','A','U','T','O',0,1,0,0,0,32,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
    auto legacy=automatic;memcpy(legacy.data(),"FXTMEM\0\0",8);
    auto run=[&](uint32_t flags,uint32_t pages,int want){
        svc::CreateProcessParameter p{flags,pages};fs::opened=fs::closed=0;
        int rc=ApplyFextendoMemoryDescriptor(&p);assert(rc==want);assert(fs::opened==fs::closed);
        assert(p.code_address==0xfeed);
        if(rc){assert(p.flags==flags&&p.system_resource_num_pages==pages);}return p;
    };
    for(uint32_t flags=0;flags<0x4000;flags++){
        fs::files.clear();auto p=run(flags,17,0);assert(p.flags==flags&&p.system_resource_num_pages==17);
        fs::files["/fxtauto"]=automatic;
        const bool valid=(flags&15)==5&&(flags&64)&&!(flags&(0x780|0x2000));
        p=run(flags,0,valid?0:2);
        if(valid){assert(svc::fextendo::CompatibleFlags(p.flags));assert(p.flags==((flags&~14u)|6u|0x40000000u));assert(p.system_resource_num_pages==4096);}
    }
    fs::files["/fxtauto"]=automatic;run(0x65,1,2);run(0x40000065,0,2);
    for(size_t i=0;i<32;i++)for(int b=0;b<8;b++){
        auto bad=automatic;bad[i]^=1<<b;fs::files["/fxtauto"]=bad;run(0x65,0,2);
    }
    for(size_t n:{size_t(0),size_t(31),size_t(33)}){auto bad=automatic;bad.resize(n);fs::files["/fxtauto"]=bad;run(0x65,0,2);}
    fs::files["/fxtauto"]=automatic;
    for(int e=1;e<=3;e++){fs::error=e;run(0x65,0,99);}fs::error=0;
    fs::short_read=1;run(0x65,0,2);fs::short_read=0;
    fs::files["/fxtmem"]=legacy;run(0x65,0,2);run(0x67,4096,2);
    fs::files.erase("/fxtauto");auto p=run(0x67,4096,0);assert(p.flags==0x40000067&&p.system_resource_num_pages==4096);
    run(0x65,0,2);
    info[0]=0x200000;info[1]=0xffe00000;info[2]=0;info[3]=0x80000000;candidate=0xa0000000;
    assert(fxt_process_mode()==32&&fxt_limit_heap(0xc0000000)==0x80000000);
    assert(fxt_find_native(0x400000)==(void*)candidate&&!reservations);
    candidate=0xfffff000;assert(!fxt_find_native(0x2000));candidate=0x100000000;assert(!fxt_find_native(4096));
    info[2]=0x40000000;assert(!fxt_process_mode()&&!fxt_find_native(4096));info[2]=0;
    info[1]=0x7fffe00000;info[3]=0x100000000;candidate=0x180000000;
    assert(fxt_process_mode()==39&&fxt_limit_heap(0xc0000000)==0xc0000000);
    reserve_fail=1;assert(!fxt_find_native(4096));reserve_fail=0;
    assert(fxt_find_native(4096)==(void*)candidate);int count=reservations;
    assert(fxt_find_native(4096)==(void*)candidate&&reservations==count);
    candidate=0xfff00000;assert(!fxt_find_native(4096));candidate=0x7ffffff000;assert(!fxt_find_native(8192));
    candidate=UINTPTR_MAX;assert(!fxt_find_native(4096));query_error=1;assert(!fxt_limit_heap(0x40000000)&&!fxt_find_native(4096));query_error=0;
    info[0]=0x8000000;info[1]=0x7ff8000000;assert(!fxt_process_mode());
    puts("PASS: 16384 flag combinations, legacy/absent/dual descriptors, every descriptor bit mutation, I/O rollback/close, 32/39 native placement, heap caps, range overflow, reservation failure");
}
