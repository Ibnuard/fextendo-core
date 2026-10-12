// SPDX-License-Identifier: GPL-2.0-or-later
#include "update.hpp"
#include "storage.hpp"
#include <algorithm>
#include <cstring>
#include <sys/statvfs.h>

namespace fxp {
namespace {
uint32_t u32(const Bytes& d,size_t p){require(p<=d.size()&&d.size()-p>=4,"Truncated NRO.");return uint32_t(d[p])|uint32_t(d[p+1])<<8|uint32_t(d[p+2])<<16|uint32_t(d[p+3])<<24;}
uint64_t u64(const Bytes& d,size_t p){return u32(d,p)|(uint64_t(u32(d,p+4))<<32);}
bool ends(const std::string& s,const std::string& tail){return s.size()>=tail.size()&&s.compare(s.size()-tail.size(),tail.size(),tail)==0;}
std::string field(const Bytes& d,size_t p,size_t n){require(p<=d.size()&&n<=d.size()-p,"Truncated NRO metadata.");auto begin=d.begin()+p,end=std::find(begin,begin+n,0);require(end!=begin+n,"Unterminated NRO metadata.");return {begin,end};}
struct Paths {std::string target,stage,backup,journal;};
Paths paths(const std::string& root,const std::string& relative){
    require(relative.compare(0,7,"switch/")==0&&relative.size()<650&&ends(relative,".nro")&&!ends(relative,".recovery.nro"),"Open the installed NRO from hbmenu to update this app.");
    const auto p=join(root,relative);return {p,p+".download",p+".recovery.nro",p+".update.json"};
}
Json record(const Paths& p){
    auto j=parseJson(readText(p.journal,4096));const auto digest=j.at("checksum").get<std::string>();j.erase("checksum");
    auto text=j.dump();require(j.at("schema")==1&&digest==hash(Bytes(text.begin(),text.end())),"Invalid app update journal. Recovery files were kept.");
    for(const char* kind:{"old","next"}){
        const auto& a=j.at(kind);const auto h=a.at("hash").get<std::string>();
        require(h.size()==64&&h.find_first_not_of("0123456789abcdef")==std::string::npos,"Invalid app update hash.");
        const auto size=a.at("size").get<uint64_t>();require(size>=0x4000&&size<=MaxNroSize,"Invalid app update size.");
        versionCompare(a.at("version"),"0.0.0");
    }
    require(versionCompare(j.at("next").at("version"),j.at("old").at("version"))>0,"Invalid app update version order.");
    return j;
}
bool is(const std::string& path,const Json& a){return matches(path,a.at("size"),a.at("hash"));}
void cleanup(const Paths& p,const Json& j){
    if(exists(p.backup))require(is(p.backup,j.at("old")),"Recovery NRO changed. Files kept.");
    removeFile(p.stage);removeFile(p.backup);removeFile(p.journal);
}
}

std::string appRelativePath(const std::string& argument){
    std::string relative=argument;
    if(relative.compare(0,6,"sdmc:/")==0)relative.erase(0,6);
    else if(!relative.empty()&&relative.front()=='/')relative.erase(0,1);
    if(ends(relative,".recovery.nro"))relative.resize(relative.size()-13);
    paths("sdmc:",relative);return relative;
}

std::string nroVersion(const Bytes& d){
    require(d.size()>=0x80&&d.size()<=MaxNroSize&&std::memcmp(d.data()+16,"NRO0",4)==0,"Invalid NRO executable.");
    require(u32(d,20)==0,"Unsupported NRO format.");
    const uint64_t body=u32(d,24);
    require(body>=0x80&&body<=d.size()&&d.size()-body>=56,"Invalid NRO asset offset.");
    uint64_t previous=0;
    for(size_t p:{0x20u,0x28u,0x30u}){
        uint64_t off=u32(d,p),size=u32(d,p+4);
        require(off>=previous&&off<=body&&size<=body-off,"Invalid NRO segment.");previous=off+size;
    }
    require(u32(d,0x20)==0&&u32(d,0x24)>=0x80,"Invalid NRO text segment.");
    require(std::memcmp(d.data()+body,"ASET",4)==0&&u32(d,body+4)==0,"NRO assets are missing.");
    uint64_t nacp=0;previous=56;
    for(size_t p:{8u,24u,40u}){
        uint64_t off=u64(d,body+p),size=u64(d,body+p+8);
        require(off>=previous&&off<=d.size()-body&&size<=d.size()-body-off,"Invalid NRO asset range.");
        require(size>0,"Incomplete NRO assets.");previous=off+size;
        if(p==24){require(size==0x4000,"Invalid NACP size.");nacp=body+off;}
        if(p==40)require(size>=0x50,"Missing NRO resources.");
    }
    require(field(d,nacp,512)=="FEXTendo Patch","Downloaded NRO belongs to another application.");
    const auto version=field(d,nacp+0x3060,16);versionCompare(version,"0.0.0");return version;
}

bool recoverAppUpdate(const std::string& root,const std::string& relative){
    const auto p=paths(root,relative);if(!exists(p.journal))return false;
    const auto j=record(p);
    if(!exists(p.target)){
        require(is(p.backup,j.at("old")),"Recovery NRO missing or changed. Recopy the app NRO.");
        moveFile(p.backup,p.target);
    }
    require(is(p.target,j.at("old"))||is(p.target,j.at("next")),"Installed NRO changed during update. Recovery files kept.");
    cleanup(p,j);return true;
}

void stageAppUpdate(const std::string& root,const std::string& relative,const std::string& version,const Asset& a,const Bytes& data,const Progress& progress){
    const auto p=paths(root,relative);progress.check();
    require(!exists(p.journal)&&!exists(p.stage)&&!exists(p.backup),"An app update needs recovery. Close and reopen this app first.");
    require(a.name=="FEXTendo-Patch.nro"&&data.size()==a.size&&hash(data)==a.hash,"Downloaded NRO SHA-256 mismatch.");
    require(nroVersion(data)==version&&versionCompare(version,AppVersion)>0,"NRO version does not match the newer release.");
    auto old=read(p.target,MaxNroSize);require(nroVersion(old)==AppVersion,"The NRO on SD differs from this running app. Reopen it before updating.");
    struct statvfs space{};require(!statvfs(root.c_str(),&space),"Could not check free SD space.");
    const uint64_t available=uint64_t(space.f_bavail)*space.f_frsize;
    require(available>=data.size()+1024*1024,"Not enough free SD space for the app update.");
    Json j={{"schema",1},{"old",{{"hash",hash(old)},{"size",old.size()},{"version",AppVersion}}},
            {"next",{{"hash",a.hash},{"size",a.size},{"version",version}}}};
    auto text=j.dump();j["checksum"]=hash(Bytes(text.begin(),text.end()));text=j.dump();
    progress.update("Saving verified app update",80);progress.check();
    writeFile(p.journal,Bytes(text.begin(),text.end()));
    writeFile(p.stage,data);require(is(p.stage,j.at("next")),"Staged NRO verification failed.");
    progress.check();progress.update("App update ready",100);
}

void publishAppUpdate(const std::string& root,const std::string& relative,const Progress& progress){
    const auto p=paths(root,relative);const auto j=record(p);
    require(is(p.target,j.at("old"))&&!exists(p.backup)&&is(p.stage,j.at("next")),"App update files changed. Close and reopen to recover.");
    progress.check();progress.update("Replacing app NRO; please wait",95);
    // No cancellation beyond this point. On FAT, rename cannot overwrite a
    // destination. Keep a launchable recovery NRO throughout the two renames.
    moveFile(p.target,p.backup);moveFile(p.stage,p.target);
    require(is(p.target,j.at("next")),"Published NRO verification failed. Recovery files kept.");
    cleanup(p,j);progress.update("App updated. Close and reopen",100);
}
}
