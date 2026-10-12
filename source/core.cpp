// SPDX-License-Identifier: GPL-2.0-or-later
#include "core.hpp"
#include "storage.hpp"
#include "generated.hpp"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>
#ifdef __SWITCH__
#include <switch.h>
#else
#include <openssl/sha.h>
#endif

namespace fxp {
void require(bool ok, const std::string& error) { if (!ok) throw std::runtime_error(error); }
void Progress::check() const { require(!cancelled || !cancelled(), "Cancelled. Installed files kept."); }
void Progress::update(const std::string& text, int p) const { if(report) report(text,p); }
void mutationPoint() {
#ifdef FXP_TEST
    static int count=0;
    const char* n=std::getenv("FXP_FAIL_AFTER");
    if(n && ++count==std::atoi(n)) std::_Exit(99);
#endif
}
static std::string hex(const uint8_t* p, size_t n) {
    static const char* chars="0123456789abcdef";
    std::string s; s.reserve(n*2);
    for(size_t i=0;i<n;i++) {s+=chars[p[i]>>4];s+=chars[p[i]&15];} return s;
}
static bool hexString(const std::string& s, size_t size) {
    return s.size()==size && s.find_first_not_of("0123456789abcdef")==std::string::npos;
}
std::string hash(const Bytes& bytes) {
    uint8_t out[32];
#ifdef __SWITCH__
    sha256CalculateHash(out, bytes.data(), bytes.size());
#else
    SHA256(bytes.data(),bytes.size(),out);
#endif
    return hex(out,32);
}
std::string join(const std::string& root, const std::string& rel) {
    require(!root.empty() && !rel.empty() && rel.front()!='/' && rel.back()!='/' &&
            rel.find('\\')==std::string::npos && rel.find(':')==std::string::npos,
            "Invalid relative path.");
    std::istringstream stream(rel); std::string part;
    while(std::getline(stream,part,'/')) require(!part.empty() && part!="." && part!="..", "Unsafe relative path.");
    return root + (root.back()=='/'?"":"/") + rel;
}
// Check every existing component, not only the leaf. Never follow links on host or SD.
static void safeParents(const std::string& path, bool create) {
    for(size_t i=1;i<path.size();i++) if(path[i]=='/') {
        const std::string part=path.substr(0,i);
        if(part.back()==':') continue;
        struct stat st{};
        if(!lstat(part.c_str(),&st)) require(S_ISDIR(st.st_mode),"Unsafe parent: "+part);
        else {
            require(errno==ENOENT,"Cannot inspect folder: "+part);
            if(create) { require(mkdir(part.c_str(),0777)==0,"Cannot create folder: "+part);mutationPoint(); }
        }
    }
}
bool exists(const std::string& p) {
    safeParents(p,false); struct stat st{};
    if(lstat(p.c_str(),&st)) { require(errno==ENOENT,"Cannot inspect file: "+p);return false; }
    require(S_ISREG(st.st_mode),"Expected a regular file: "+p);return true;
}
Bytes read(const std::string& p, size_t limit) {
    require(exists(p), "Missing file: "+p);
    struct stat st{}; require(!stat(p.c_str(),&st) && st.st_size>=0 && uint64_t(st.st_size)<=limit,"Invalid file size: "+p);
    FILE* f=fopen(p.c_str(),"rb");require(f!=nullptr,"Cannot read: "+p);
    Bytes b(size_t(st.st_size));size_t n=fread(b.data(),1,b.size(),f);bool ok=!ferror(f) && n==b.size();
    ok=fclose(f)==0 && ok;require(ok,"Read failed: "+p);return b;
}
std::string readText(const std::string& p, size_t max) {auto b=read(p,max);return std::string(b.begin(),b.end());}
bool matches(const std::string& p, uint64_t size, const std::string& sha) {
    if(!exists(p)) return false;
    struct stat st{}; if(stat(p.c_str(),&st) || uint64_t(st.st_size)!=size)return false;
    return hash(read(p,size))==sha;
}
static void syncSd() {
#ifdef __SWITCH__
    require(R_SUCCEEDED(fsdevCommitDevice("sdmc")),"SD commit failed. Reopen the installer to recover.");
#else
    // fsync every file and rename's parent for durable tests on ordinary filesystems.
#endif
    mutationPoint();
}
static void syncParent(const std::string& p) {
#ifndef __SWITCH__
    const std::string dir=p.substr(0,p.find_last_of('/'));
    FILE* f=fopen(dir.c_str(),"r"); if(f){fsync(fileno(f));fclose(f);}
#else
    (void)p;
#endif
    syncSd();
}
void writeFile(const std::string& p,const Bytes& data) {
    safeParents(p,true); if(exists(p)) require(false,"Staging file already exists: "+p);
    FILE* f=fopen(p.c_str(),"wb");require(f!=nullptr,"Cannot write: "+p);
    bool ok=fwrite(data.data(),1,data.size(),f)==data.size();
    if(fflush(f)!=0)ok=false;
    if(fsync(fileno(f))!=0)ok=false;
    if(fclose(f)!=0)ok=false;
    require(ok,"SD write failed: "+p);mutationPoint();syncParent(p);
}
static Bytes bytes(const std::string& s){return Bytes(s.begin(),s.end());}
void moveFile(const std::string& from,const std::string& to) {
    require(exists(from),"Missing staged file.");safeParents(to,true);
    require(!exists(to),"Refusing to replace an unverified file: "+to);
    require(!rename(from.c_str(),to.c_str()),"SD rename failed. Reopen installer to recover.");
    mutationPoint();syncParent(to);
}
void removeFile(const std::string& p) {
    if(exists(p)){require(!unlink(p.c_str()),"Cannot remove staging file: "+p);mutationPoint();syncParent(p);}
}
static unsigned parseVersion(const std::string& s) {
    require(!s.empty()&&s.size()<16,"Invalid version.");
    unsigned n=0;std::istringstream in(s);std::string item;int parts=0;
    while(std::getline(in,item,'.')) {
        require(!item.empty()&&item.size()<=3 && item.find_first_not_of("0123456789")==std::string::npos,"Invalid version: "+s);
        unsigned v=unsigned(std::stoul(item));require(v<=255,"Invalid version: "+s);n=(n<<8)|v;parts++;
    }
    require(parts==3 && s.back()!='.',"Expected major.minor.patch: "+s);return n;
}
int versionCompare(const std::string& a,const std::string& b){auto x=parseVersion(a),y=parseVersion(b);return x<y?-1:x>y?1:0;}
Json parseJson(const std::string& s) {
    require(s.size()<=512*1024,"Manifest is too large.");
    std::vector<std::vector<std::string>> keys;
    return Json::parse(s,[&](int depth,Json::parse_event_t event,Json& value){
        require(depth<=24,"JSON nesting too deep.");
        if(event==Json::parse_event_t::object_start) keys.emplace_back();
        if(event==Json::parse_event_t::key){auto k=value.get<std::string>();require(std::find(keys.back().begin(),keys.back().end(),k)==keys.back().end(),"Duplicate JSON key.");keys.back().push_back(k);}
        if(event==Json::parse_event_t::object_end)keys.pop_back();
        return true;
    });
}
static Asset parseAsset(const Json& j) {
    Asset a;a.name=j.at("asset").get<std::string>();a.hash=j.at("sha256").get<std::string>();a.size=j.at("bytes").get<uint64_t>();
    require(a.name.size()>=4&&a.name.size()<90 && a.name.front()!='.' && a.name.find("..") == std::string::npos &&
            a.name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")==std::string::npos,"Unsafe asset name.");
    require(hexString(a.hash,64)&&a.size>=64&&a.size<=16*1024*1024,"Invalid asset size/hash.");return a;
}
static Bundle parseBundle(const Json& j) {
    Bundle b;b.version=j.at("version");b.atmosphere=j.at("atmosphere");b.revision=j.at("revision");b.hoc=j.at("hoc");b.hos=j.at("tested_hos");
    b.loaderKind=j.value("loader_kind",std::string("hoc"));
    require(b.loaderKind=="stock"||b.loaderKind=="hoc","Unknown loader kind.");
    parseVersion(b.version);parseVersion(b.atmosphere);parseVersion(b.hos);
    require(hexString(b.revision,8),"Invalid Atmosphere source revision.");
    if(b.loaderKind=="hoc") {
        parseVersion(b.hoc);
        require(j.at("hoc_configuration")=="official-release-default","Only official HOC defaults are accepted.");
    } else require(b.hoc.empty()&&j.at("hoc_configuration")=="not-applicable","Standard loader must not contain HOC settings.");
    b.kernel=parseAsset(j.at("kernel"));b.loader=parseAsset(j.at("loader"));
    require(b.kernel.name!=b.loader.name,"Kernel and loader must be separate assets.");return b;
}
Catalog parseCatalog(const std::string& text) {
    const auto j=parseJson(text);Catalog c;
    require(j.at("schema")==1&&j.at("application")=="fextendo-patch"&&j.at("abi")=="fxtmem-v1","Unsupported patch catalog.");
    require(versionCompare(j.at("min_app_version"),AppVersion)<=0,"This catalog needs a newer FEXTendo Patch NRO.");
    c.version=j.at("catalog_version");parseVersion(c.version);
    const auto& list=j.at("bundles");require(list.is_array()&&list.size()>0&&list.size()<=32,"Invalid bundle list.");
    for(const auto& item:list){Bundle b=parseBundle(item);for(const auto& old:c.bundles)require(b.atmosphere!=old.atmosphere||b.loaderKind!=old.loaderKind,"Duplicate Atmosphere/loader bundle.");c.bundles.push_back(b);}return c;
}
Json bundleJson(const Bundle& b) {
    auto asset=[](const Asset& a){return Json{{"asset",a.name},{"bytes",a.size},{"sha256",a.hash}};};
    Json j={{"version",b.version},{"atmosphere",b.atmosphere},{"revision",b.revision},{"hoc",b.hoc},{"tested_hos",b.hos},
            {"hoc_configuration",b.loaderKind=="hoc"?"official-release-default":"not-applicable"},{"kernel",asset(b.kernel)},{"loader",asset(b.loader)}};
    // Preserve the identity of published legacy HOC bundles and installed entries.
    if(b.loaderKind!="hoc")j["loader_kind"]=b.loaderKind;
    return j;
}
std::string loaderLabel(const Bundle& b){return b.loaderKind=="stock"?"Standard / sys-clk":"HOC "+b.hoc;}
void mergeCatalog(Catalog& current,const Catalog& update) {
    Catalog merged=current;
    for(const auto& fresh:update.bundles) {
        auto it=std::find_if(merged.bundles.begin(),merged.bundles.end(),[&](const auto& b){return b.atmosphere==fresh.atmosphere&&b.loaderKind==fresh.loaderKind;});
        if(it==merged.bundles.end())merged.bundles.push_back(fresh);
        else if(versionCompare(fresh.version,it->version)>0)*it=fresh;
        else if(versionCompare(fresh.version,it->version)==0)require(bundleId(fresh)==bundleId(*it),"Release changed a published bundle without increasing its version.");
    }
    current=std::move(merged);
}
std::string bundleId(const Bundle& b){return hash(bytes(bundleJson(b).dump())).substr(0,32);}
Catalog loadCatalog(const std::string& romfs) {
    auto b=read(join(romfs,"catalog.json"),512*1024);
    require(hash(b)==FXP_CATALOG_HASH,"Bundled catalog verification failed. Recopy the NRO.");
    return parseCatalog(std::string(b.begin(),b.end()));
}
static std::string trim(std::string s) {
    auto first=s.find_first_not_of(" \t\r\n");if(first==std::string::npos)return "";
    return s.substr(first,s.find_last_not_of(" \t\r\n")-first+1);
}
static std::string ini(const std::string& text,const std::string& section,const std::string& key) {
    std::string active,line,value;bool seen=false;std::istringstream in(text);
    while(std::getline(in,line)) {
        line=trim(line);if(line.empty()||line[0]=='#'||line[0]==';')continue;
        if(line.front()=='['&&line.back()==']'){active=line.substr(1,line.size()-2);continue;}
        size_t pos=line.find('=');if(active==section&&pos!=std::string::npos&&trim(line.substr(0,pos))==key){
            require(!seen,"Duplicate INI key: "+key);seen=true;value=trim(line.substr(pos+1));}
    }return value;
}
static uint32_t u32(const Bytes& b,size_t p){return b[p]|uint32_t(b[p+1])<<8|uint32_t(b[p+2])<<16|uint32_t(b[p+3])<<24;}
std::string bootEntry(const std::string& base,const Bundle& b) {
    return std::string("# Managed by FEXTendo Patch. ")+(b.loaderKind=="hoc"?"HOC official defaults.":"Standard loader; no HOC.")+"\n# Bundle " + b.version + " / Atmosphere " + b.atmosphere +
        "\n[FEXTendo Patch (emuMMC)]\nid=fxtpat1\npkg3=atmosphere/package3\nkernel="+base+"/mesosphere.bin\nkip1="+base+
        "/loader.kip\nemummcforce=1\nicon="+base+"/icon.bmp\nlogopath="+base+"/boot.bmp\n";
}
static bool validBase(const std::string& base) {
    const std::string prefix="atmosphere/fextendo/patch/";
    if(base.compare(0,prefix.size(),prefix)!=0)return false;
    std::string leaf=base.substr(prefix.size());
    if(leaf.size()>32){if(leaf.size()>37||leaf.substr(32,2)!="-r"||leaf.substr(34).empty()||leaf.substr(34).find_first_not_of("0123456789")!=std::string::npos)return false;leaf.resize(32);}
    return hexString(leaf,32);
}
static std::string installedBase(const std::string& root) {
    auto path=join(root,EntryPath);if(!exists(path))return "";
    auto text=readText(path,16384);auto k=ini(text,"FEXTendo Patch (emuMMC)","kernel");
    const std::string end="/mesosphere.bin";
    if(k.size()<end.size()||k.substr(k.size()-end.size())!=end)return "";
    auto base=k.substr(0,k.size()-end.size());return validBase(base)?base:"";
}
static bool verifyPayload(const std::string& root,const std::string& base,const Bundle& b) {
    return matches(join(root,base+"/mesosphere.bin"),b.kernel.size,b.kernel.hash)&&
           matches(join(root,base+"/loader.kip"),b.loader.size,b.loader.hash)&&
           matches(join(root,base+"/icon.bmp"),147510,FXP_ICON_HASH)&&
           matches(join(root,base+"/boot.bmp"),1536054,FXP_BOOT_HASH);
}
bool pending(const std::string& root){return exists(join(root,std::string(StateDir)+"/transaction.json"));}
Status inspect(const std::string& root,const Environment& env,const Catalog& catalog,const std::string& requested) {
    Status s;s.running=env.atmosphereKnown?env.atmosphere:"Unavailable";s.hos=env.hos;
    try {
        require(requested=="auto"||requested=="stock"||requested=="hoc","Unknown loader selection.");
        if(requested!="auto")s.loaderKind=requested;
        if(pending(root)) {s.recovery=true;s.headline="Installation interrupted";s.detail="Select Recover installation before making other changes.";return s;}
        require(env.atmosphereKnown,"Could not read the running Atmosphere version. Launch under Atmosphere.");
        parseVersion(env.atmosphere);
        const auto pkg=read(join(root,"atmosphere/package3"),32*1024*1024);
        require(pkg.size()>=64&&memcmp(pkg.data(),"PK31",4)==0&&memcmp(pkg.data()+32,"FSS0",4)==0&&u32(pkg,36)==pkg.size(),"atmosphere/package3 is missing, incomplete or invalid.");
        s.disk=std::to_string(pkg[59])+"."+std::to_string(pkg[58])+"."+std::to_string(pkg[57]);
        std::ostringstream rev;rev<<std::hex<<std::setw(8)<<std::setfill('0')<<u32(pkg,60);s.revision=rev.str();
        require(s.running==s.disk,"Running Atmosphere and SD package3 differ. Reboot into the matching Atmosphere first.");
        // A verified previous installation is still recognized after restarting the app.
        const std::string base=installedBase(root);Bundle previous;bool havePrevious=false;
        if(!base.empty()&&exists(join(root,base+"/bundle.json"))) {
            previous=parseBundle(parseJson(readText(join(root,base+"/bundle.json"),8192)));
            havePrevious=base.substr(std::string("atmosphere/fextendo/patch/").size(),32)==bundleId(previous) && previous.atmosphere==s.disk;
        }
        if(havePrevious&&requested=="auto")s.loaderKind=previous.loaderKind;
        for(const auto& b:catalog.bundles) if(b.atmosphere==s.running&&b.loaderKind==s.loaderKind){s.bundle=b;s.supported=true;break;}
        bool previousSelected=havePrevious&&previous.loaderKind==s.loaderKind;
        if(previousSelected&&s.supported&&versionCompare(previous.version,s.bundle.version)==0)
            require(bundleId(previous)==bundleId(s.bundle),"Published bundle changed without a version increase. Check the release.");
        if(previousSelected && (!s.supported||versionCompare(previous.version,s.bundle.version)>0)){s.bundle=previous;s.supported=true;}
        require(s.supported,"No "+s.loaderKind+" patch for Atmosphere "+s.running+". Select Check update.");
        s.revisionMatches=s.bundle.revision==s.revision;
        if(exists(join(root,"emuMMC/emummc.ini")))s.emummc=ini(readText(join(root,"emuMMC/emummc.ini"),32768),"emummc","enabled")=="1"?"Enabled":"Disabled";
        else s.emummc="Missing";
        require(s.emummc=="Enabled","Enable emuMMC in Hekate before installing this package.");
        require(exists(join(root,"bootloader/sys/nyx.bin"))&&exists(join(root,"bootloader/sys/emummc.kipm")),"Hekate/Nyx files are incomplete. Update Hekate first.");
        if(havePrevious && readText(join(root,EntryPath),16384)==bootEntry(base,previous) && verifyPayload(root,base,previous)) {
            s.installation="v"+previous.version+" installed";
            s.installed=bundleId(previous)==bundleId(s.bundle);
        } else if(exists(join(root,EntryPath)))s.installation="Needs repair / entry changed";
        s.ready=true;s.headline=s.installed?"Patch installed":"Ready to install";
        s.detail=s.installed?"Boot Hekate > More configs > FEXTendo Patch (emuMMC).":"Patch available for this Atmosphere version. Choose a loader below.";
        if(!s.revisionMatches)s.detail+=" Different source revision detected; version-based installation is allowed.";
    } catch(const std::exception& e){s.headline=s.supported?"Setup needed":"Not supported";s.detail=e.what();}
    return s;
}
static std::string state(const std::string& root,const char* name){return join(root,std::string(StateDir)+"/"+name);}
static std::string stagedEntry(const std::string& root){return join(root,"bootloader/ini/.fextendo-patch-new");}
static std::string oldEntry(const std::string& root){return join(root,"bootloader/ini/.fextendo-patch-old");}
static std::string digestFile(const std::string& p){return hash(read(p,16384));}
static void saveBackup(const std::string& root,const std::string& oldHash) {
    auto old=oldEntry(root); if(!exists(old))return;
    require(digestFile(old)==oldHash,"Previous boot entry changed. Recovery stopped.");
    const std::string target=state(root,("backup-"+oldHash.substr(0,16)+".ini").c_str());
    if(exists(target))require(digestFile(target)==oldHash,"Backup mismatch. Recovery stopped.");
    else writeFile(target,read(old,16384));
    removeFile(old);
}
void recover(const std::string& root,const Progress& p) {
    const std::string journal=state(root,"transaction.json");require(exists(journal),"No pending installation.");
    auto j=parseJson(readText(journal,8192));auto checksum=j.at("checksum").get<std::string>();j.erase("checksum");
    require(hash(bytes(j.dump()))==checksum&&j.at("schema")==1,"Recovery journal is invalid. Keep files for manual recovery.");
    bool had=j.at("had_entry");std::string before=j.at("before"),after=j.at("after");
    require(hexString(after,64)&&(!had?before.empty():hexString(before,64)),"Invalid recovery hashes.");
    auto entry=join(root,EntryPath);auto old=oldEntry(root);
    p.update("Recovering boot entry",80);
    if(exists(entry)&&digestFile(entry)==after) {
        // A fully written new entry is the commit point. Payloads were durable first.
        const auto base=installedBase(root);
        require(!base.empty(),"Published entry has an invalid path. Recovery stopped.");
        const auto bundle=parseBundle(parseJson(readText(join(root,base+"/bundle.json"),8192)));
        require(base.substr(std::string("atmosphere/fextendo/patch/").size(),32)==bundleId(bundle)&&
                readText(entry,16384)==bootEntry(base,bundle)&&verifyPayload(root,base,bundle),
                "Published payload is damaged. Keep the previous entry backup for manual recovery.");
        if(had)saveBackup(root,before);else require(!exists(old),"Unexpected previous entry. Recovery stopped.");
    } else {
        if(exists(entry))require(had&&digestFile(entry)==before,"Boot entry was changed outside the installer. Recovery stopped.");
        if(had&&!exists(entry)) {
            require(exists(old)&&digestFile(old)==before,"Previous entry backup is missing. Recovery stopped.");
            moveFile(old,entry);
        } else if(exists(old)) {
            require(had&&digestFile(old)==before,"Unexpected previous entry. Recovery stopped.");removeFile(old);
        }
    }
    removeFile(stagedEntry(root));removeFile(journal);removeFile(state(root,"transaction.tmp"));p.update("Recovery complete",100);
}
static void checkBinary(const Bundle& b,const Bytes& kernel,const Bytes& loader) {
    require(kernel.size()==b.kernel.size&&hash(kernel)==b.kernel.hash,"Kernel SHA-256 mismatch. Boot files unchanged.");
    require(loader.size()==b.loader.size&&hash(loader)==b.loader.hash,"Loader SHA-256 mismatch. Boot files unchanged.");
    require(loader.size()>=256&&memcmp(loader.data(),"KIP1",4)==0&&u32(loader,16)==1&&u32(loader,20)==0x01000000,"Asset is not a loader KIP.");
    require(kernel.size()>=64&&memcmp(kernel.data()+4,"MSS1",4)==0,"Asset is not a Mesosphere kernel.");
}
void install(const std::string& root,const std::string& romfs,const Environment& env,const Catalog& c,
             const Bundle& b,const Bytes& kernel,const Bytes& loader,const Progress& p) {
    p.check();p.update("Checking compatibility and SHA-256",10);
    auto s=inspect(root,env,c,b.loaderKind);require(s.ready&&!s.recovery,s.detail);
    require(bundleId(s.bundle)==bundleId(b),"Selected bundle changed. Refresh status.");
    require(!s.installed,"This patch is already installed.");checkBinary(b,kernel,loader);
    auto icon=read(join(romfs,"boot/fextendo-memory.bmp"),147510),boot=read(join(romfs,"boot/fextendo-boot.bmp"),1536054);
    require(hash(icon)==FXP_ICON_HASH&&hash(boot)==FXP_BOOT_HASH,"Bundled artwork failed verification.");
    struct statvfs space{};require(statvfs(root.c_str(),&space)==0,"Cannot check SD space.");
    uint64_t free=uint64_t(space.f_bavail)*space.f_frsize;
    require(free>=kernel.size()+loader.size()+icon.size()+boot.size()+8*1024*1024,"At least 12 MiB of free SD space is needed.");
    require(!exists(oldEntry(root)),"Orphan backup found. Keep .fextendo-patch-old for manual recovery.");
    removeFile(stagedEntry(root));removeFile(state(root,"transaction.tmp"));
    std::string base="atmosphere/fextendo/patch/"+bundleId(b);
    // Never modify an existing boot pair, even if its files are incomplete/corrupt.
    const std::string original=base;
    for(int i=0;;i++) {
        require(i<100,"Too many staging attempts. Inspect the patch folder.");
        struct stat st{};auto dir=join(root,base);safeParents(dir+"/check",false);
        if(lstat(dir.c_str(),&st)){require(errno==ENOENT,"Cannot inspect payload directory.");break;}
        base=original+"-r"+std::to_string(i+1);
    }
    p.check();p.update("Writing isolated boot files",25);
    writeFile(join(root,base+"/mesosphere.bin"),kernel);p.check();
    writeFile(join(root,base+"/loader.kip"),loader);p.check();
    writeFile(join(root,base+"/icon.bmp"),icon);writeFile(join(root,base+"/boot.bmp"),boot);
    writeFile(join(root,base+"/bundle.json"),bytes(bundleJson(b).dump(2)+"\n"));
    require(verifyPayload(root,base,b),"SD verification failed. Existing entry kept.");p.check();
    // Recheck prerequisites immediately before publishing the new entry.
    auto fresh=inspect(root,env,c,b.loaderKind);require(fresh.ready&&bundleId(fresh.bundle)==bundleId(b)&&fresh.revision==s.revision,"SD setup changed during installation.");
    auto entry=join(root,EntryPath);const bool had=exists(entry);const std::string before=had?digestFile(entry):"";
    const auto text=bootEntry(base,b);writeFile(stagedEntry(root),bytes(text));
    const std::string after=hash(bytes(text));Json j={{"schema",1},{"had_entry",had},{"before",before},{"after",after}};
    j["checksum"]=hash(bytes(j.dump()));
    writeFile(state(root,"transaction.tmp"),bytes(j.dump()+"\n"));p.check();
    p.update("Finishing installation - keep the SD connected",85);
    moveFile(state(root,"transaction.tmp"),state(root,"transaction.json"));
    require(exists(entry)==had&&(!had||digestFile(entry)==before),"Boot entry changed. Reopen installer to recover.");
    if(had)moveFile(entry,oldEntry(root));
    moveFile(stagedEntry(root),entry);require(digestFile(entry)==after,"Boot entry verification failed. Reopen to recover.");
    recover(root,p);
    p.update("Installed. Reboot into the FEXTendo Patch entry in Hekate.",100);
}
std::string readRepository(const std::string& root) {
    std::string repo;
#ifdef FXP_DEFAULT_REPOSITORY
    repo=FXP_DEFAULT_REPOSITORY;
#endif
    auto p=state(root,"update.ini");if(exists(p))repo=ini(readText(p,4096),"updates","repository");
    if(repo.empty())return repo;
    auto slash=repo.find('/');require(slash>0&&slash<repo.size()-1&&repo.find('/',slash+1)==std::string::npos&&repo.size()<140 &&
        repo.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/")==std::string::npos&&
        repo.find("..") == std::string::npos,"Invalid update repository. Use owner/repo in update.ini.");
    return repo;
}
}
