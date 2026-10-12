// Host driver for the same core, updater validation and software UI compiled in the NRO.
#include "core.hpp"
#include "update.hpp"
#include "ui.hpp"
#include <cstdio>
#include <iostream>
using namespace fxp;
int main(int argc,char** argv){
    try{
        require(argc>=4,"usage: driver command sd-root romfs [argument]");
        std::string command=argv[1],root=argv[2],romfs=argv[3];
        auto catalog=loadCatalog(romfs);Environment env{"1.11.2","22.5.0",true};
        std::string loaderKind=getenv("FXP_LOADER")?getenv("FXP_LOADER"):"auto";
        if(command=="install-catalog"){require(argc==5,"catalog file required");catalog=parseCatalog(readText(argv[4]));command="install";}
        if(const char* v=getenv("FXP_RUNNING_AMS")){env.atmosphere=v;env.atmosphereKnown=env.atmosphere!="unknown";}
        if(const char* v=getenv("FXP_RUNNING_HOS"))env.hos=v;
        if(command=="catalog"){
            require(argc==5,"catalog file required");auto c=parseCatalog(readText(argv[4]));std::cout<<c.bundles.size()<<"\n";
        }else if(command=="merge-catalog"){
            require(argc==5,"catalog file required");mergeCatalog(catalog,parseCatalog(readText(argv[4])));
            Json result=Json::array();for(const auto& b:catalog.bundles)result.push_back(bundleJson(b));std::cout<<result.dump()<<"\n";
        }else if(command=="release"){
            require(argc==6,"release metadata and manifest required");std::string tag;auto a=releaseAssets("owner/repo",readText(argv[4]),tag);
            auto c=verifyReleaseCatalog(read(argv[5],512*1024),a);std::cout<<c.bundles.size()<<"\n";
        }else if(command=="repository")std::cout<<readRepository(root)<<"\n";
        else if(command=="update-metadata"){
            require(argc==6,"release metadata and manifest required");std::string tag;
            auto assets=releaseAssets("owner/repo",readText(argv[4]),tag);
            auto u=verifyUpdate(read(argv[5],512*1024),assets,tag);
            std::cout<<Json{{"available",u.appAvailable},{"required",u.appRequired},{"has_catalog",u.hasCatalog},{"version",u.appVersion}}.dump()<<"\n";
        }else if(command=="app-target"){
            require(argc==5,"launch argument required");std::cout<<appRelativePath(argv[4])<<"\n";
        }else if(command=="nro-info"){
            require(argc==5,"NRO file required");std::cout<<nroVersion(read(argv[4],MaxNroSize))<<"\n";
        }else if(command=="app-recover"){
            require(argc==5,"NRO relative path required");std::cout<<recoverAppUpdate(root,argv[4])<<"\n";
        }else if(command=="app-publish"){
            require(argc==5,"NRO relative path required");publishAppUpdate(root,argv[4],{});
        }else if(command=="app-stage"||command=="app-install"){
            require(argc==7,"NRO relative path, new NRO and version required");auto data=read(argv[5],MaxNroSize);
            Asset a{"FEXTendo-Patch.nro",hash(data),"",data.size()};
            if(const auto* value=getenv("FXP_NRO_HASH"))a.hash=value;
            int checks=0;Progress p;if(const auto* value=getenv("FXP_CANCEL_AFTER")){
                const int threshold=std::atoi(value);p.cancelled=[&,threshold]{return ++checks>threshold;};
            }
            stageAppUpdate(root,argv[4],argv[6],a,data,p);
            if(command=="app-install")publishAppUpdate(root,argv[4],p);
        }
        else if(command=="check-update"){
            auto u=checkUpdate(readRepository(root),{});size_t verified=0;
            for(const auto& b:u.catalog.bundles){download(b.kernel,{});download(b.loader,{});verified+=2;}
            std::cout<<Json{{"tag",u.tag},{"bundles",u.catalog.bundles.size()},{"verified_downloads",verified}}.dump()<<"\n";
        }
        else if(command=="download"){
            require(argc==5,"asset JSON required");auto a=parseJson(readText(argv[4]));Asset asset{a["name"],a["sha256"],a["url"],a["bytes"]};auto b=download(asset,{});std::cout<<b.size()<<"\n";
        }else if(command=="recover")recover(root,{});
        else if(command=="install"||command=="cancel"){
            auto s=inspect(root,env,catalog,loaderKind);require(s.ready,s.detail);auto b=s.bundle;
            auto k=read(join(romfs,"boot/"+b.kernel.name),16*1024*1024),l=read(join(romfs,"boot/"+b.loader.name),16*1024*1024);
            Progress p;if(command=="cancel")p.cancelled=[] {return true;};install(root,romfs,env,catalog,b,k,l,p);
        }else if(command=="render"){
            require(argc>=5,"output file required");View v;v.status=inspect(root,env,catalog,loaderKind);v.repository=readRepository(root);v.updateText="Official update source configured";
            if(argc>=6){std::string mode=argv[5];if(mode=="confirm"){v.confirm=true;v.title="Install FEXTendo Patch?";v.detail=std::string("Install patch v")+v.status.bundle.version+" for Atmosphere "+v.status.bundle.atmosphere+" using "+loaderLabel(v.status.bundle)+". Adds or updates FEXTendo Patch (emuMMC). Reboot through Hekate to activate.";}
                if(mode=="progress"){v.busy=true;v.title="Installing patch";v.progress="Writing isolated boot files";v.percent=48;}
                if(mode=="error"){v.message=true;v.title="Operation not completed";v.detail="Update source is not configured. Set repository=owner/repo in switch/fextendo-patch/update.ini.";}}
            if(argc>=6&&std::string(argv[5])=="app-confirm"){
                v.appUpdateAvailable=true;v.appConfirm=true;v.confirm=true;v.title="Update app to v1.4.0?";
                v.detail=std::string("Current app: v")+AppVersion+". Download and install FEXTendo Patch v1.4.0 from GitHub, then exit and reopen the app. Your boot patch and settings stay as they are.";
            }
            if(argc>=6&&std::string(argv[5])=="app-complete"){
                v.message=true;v.success=true;v.exitRequired=true;v.title="Completed";
                v.detail="App updated to v1.4.0. Exit and reopen FEXTendo Patch to use it. To update the boot patch, select Install patch after reopening, then reboot through Hekate.";
            }
            Ui ui(romfs);std::vector<uint32_t> pixels(1280*720);ui.draw(pixels.data(),1280,v);
            FILE* f=fopen(argv[4],"wb");require(f!=nullptr,"Cannot write preview");fprintf(f,"P6\n1280 720\n255\n");for(auto c:pixels){unsigned char p[]={uint8_t(c),uint8_t(c>>8),uint8_t(c>>16)};fwrite(p,1,3,f);}fclose(f);
        }else if(command=="status"){
            auto s=inspect(root,env,catalog,loaderKind);std::cout<<Json{{"ready",s.ready},{"supported",s.supported},{"installed",s.installed},{"recovery",s.recovery},{"headline",s.headline},{"detail",s.detail},{"running",s.running},{"disk",s.disk},{"bundle",s.bundle.version},{"kernel",s.bundle.kernel.name},{"loader",s.bundle.loader.name},{"hos",s.hos},{"loader_kind",s.loaderKind},{"revision",s.revision},{"revision_matches",s.revisionMatches}}.dump()<<"\n";
        }else require(false,"Unknown command");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
