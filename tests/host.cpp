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
        if(command=="install-catalog"){require(argc==5,"catalog file required");catalog=parseCatalog(readText(argv[4]));command="install";}
        if(const char* v=getenv("FXP_RUNNING_AMS")){env.atmosphere=v;env.atmosphereKnown=env.atmosphere!="unknown";}
        if(command=="catalog"){
            require(argc==5,"catalog file required");auto c=parseCatalog(readText(argv[4]));std::cout<<c.bundles.size()<<"\n";
        }else if(command=="release"){
            require(argc==6,"release metadata and manifest required");std::string tag;auto a=releaseAssets("owner/repo",readText(argv[4]),tag);
            auto c=verifyReleaseCatalog(read(argv[5],512*1024),a);std::cout<<c.bundles.size()<<"\n";
        }else if(command=="repository")std::cout<<readRepository(root)<<"\n";
        else if(command=="check-update"){
            auto u=checkUpdate(readRepository(root),{});size_t verified=0;
            for(const auto& b:u.catalog.bundles){download(b.kernel,{});download(b.loader,{});verified+=2;}
            std::cout<<Json{{"tag",u.tag},{"bundles",u.catalog.bundles.size()},{"verified_downloads",verified}}.dump()<<"\n";
        }
        else if(command=="download"){
            require(argc==5,"asset JSON required");auto a=parseJson(readText(argv[4]));Asset asset{a["name"],a["sha256"],a["url"],a["bytes"]};auto b=download(asset,{});std::cout<<b.size()<<"\n";
        }else if(command=="recover")recover(root,{});
        else if(command=="install"||command=="cancel"){
            auto s=inspect(root,env,catalog);require(s.ready,s.detail);auto b=s.bundle;
            auto k=read(join(romfs,"boot/"+b.kernel.name),16*1024*1024),l=read(join(romfs,"boot/"+b.loader.name),16*1024*1024);
            Progress p;if(command=="cancel")p.cancelled=[] {return true;};install(root,romfs,env,catalog,b,k,l,p);
        }else if(command=="render"){
            require(argc>=5,"output file required");View v;v.status=inspect(root,env,catalog);v.repository=readRepository(root);v.updateText="Official update source configured";
            if(argc>=6){std::string mode=argv[5];if(mode=="confirm"){v.confirm=true;v.title="Install FEXTendo Patch?";v.detail=std::string("Install patch v")+catalog.bundles.front().version+" for Atmosphere 1.11.2 with HOC 2.5.1 official defaults. Adds a separate FEXTendo Patch (emuMMC) boot entry. Your existing boot settings are kept. A reboot through Hekate is required after installation.";}
                if(mode=="progress"){v.busy=true;v.title="Installing patch";v.progress="Writing isolated boot files";v.percent=48;}
                if(mode=="error"){v.message=true;v.title="Operation not completed";v.detail="Update source is not configured. Set repository=owner/repo in switch/fextendo-patch/update.ini.";}}
            Ui ui(romfs);std::vector<uint32_t> pixels(1280*720);ui.draw(pixels.data(),1280,v);
            FILE* f=fopen(argv[4],"wb");require(f!=nullptr,"Cannot write preview");fprintf(f,"P6\n1280 720\n255\n");for(auto c:pixels){unsigned char p[]={uint8_t(c),uint8_t(c>>8),uint8_t(c>>16)};fwrite(p,1,3,f);}fclose(f);
        }else if(command=="status"){
            auto s=inspect(root,env,catalog);std::cout<<Json{{"ready",s.ready},{"supported",s.supported},{"installed",s.installed},{"recovery",s.recovery},{"headline",s.headline},{"detail",s.detail},{"running",s.running},{"disk",s.disk}}.dump()<<"\n";
        }else require(false,"Unknown command");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
