// SPDX-License-Identifier: GPL-2.0-or-later
#include <switch.h>
#include <atomic>
#include <algorithm>
#include <cstdio>
#include <exception>
#include <stdexcept>
#include "core.hpp"
#include "update.hpp"
#include "ui.hpp"

namespace {
using namespace fxp;
constexpr const char* Root="sdmc:";
constexpr const char* Romfs="romfs:";
Environment runningEnvironment() {
    Environment e;u64 value=0;
    if(R_SUCCEEDED(splInitialize())) {
        e.atmosphereKnown=R_SUCCEEDED(splGetConfig(static_cast<SplConfigItem>(65000),&value));splExit();
        if(e.atmosphereKnown)e.atmosphere=std::to_string((value>>56)&255)+"."+std::to_string((value>>48)&255)+"."+std::to_string((value>>40)&255);
    }
    const u32 h=hosversionGet();e.hos=std::to_string((h>>16)&255)+"."+std::to_string((h>>8)&255)+"."+std::to_string(h&255);return e;
}
enum class Operation { Refresh, Install, Update, Recover, UpdateApp, PublishApp };
struct Job {
    Thread thread{};
    Mutex lock{};
    std::atomic<bool> done{false}, cancel{false};
    Operation operation=Operation::Refresh;
    Catalog catalog;
    Bundle selected;
    Status status;
    Update update;
    std::string appPath;
    std::string repository, outcome, updateText, progress, loaderKind="auto";
    int percent=0;
    bool success=false;
};
void worker(void* ptr) {
    auto& j=*static_cast<Job*>(ptr);
    Progress p;
    p.cancelled=[&]{return j.cancel.load(std::memory_order_relaxed);};
    p.report=[&](const std::string& msg,int percent){mutexLock(&j.lock);j.progress=msg;j.percent=std::clamp(percent,0,100);mutexUnlock(&j.lock);};
    try {
        auto env=runningEnvironment();
        if(j.operation==Operation::Refresh) {
            p.update("Verifying system and installed files",15);
            j.repository=readRepository(Root);
        } else if(j.operation==Operation::Update) {
            j.repository=readRepository(Root);auto u=checkUpdate(j.repository,p);
            // Retain offline bundles omitted by a new release; do not downgrade an existing candidate.
            if(u.hasCatalog)mergeCatalog(j.catalog,u.catalog);
            j.update=u;
            j.updateText="Checked "+u.tag+" on GitHub";
            j.outcome=u.appAvailable?"App v"+u.appVersion+" is available. Select Update app to download and install it.":"Catalog verified. Select Install patch if a compatible update is available.";
        } else if(j.operation==Operation::UpdateApp) {
            require(!j.appPath.empty(),"Open the installed SD NRO from hbmenu to update this app.");
            require(j.update.appAvailable,"Check for a newer app release first.");
            auto data=download(j.update.app,p);
            stageAppUpdate(Root,j.appPath,j.update.appVersion,j.update.app,data,p);
        } else if(j.operation==Operation::PublishApp) {
            publishAppUpdate(Root,j.appPath,p);
            j.outcome="App updated to v"+j.update.appVersion+". Exit and reopen FEXTendo Patch to use it. To update the boot patch, select Install patch after reopening, then reboot through Hekate.";
        } else if(j.operation==Operation::Recover) {
            recover(Root,p);j.outcome="Recovery completed. Status has been refreshed.";
        } else {
            const auto& b=j.selected;Bytes kernel,loader;
            if(b.online){kernel=download(b.kernel,p);loader=download(b.loader,p);}
            else {kernel=read(join(Romfs,"boot/"+b.kernel.name),16*1024*1024);loader=read(join(Romfs,"boot/"+b.loader.name),16*1024*1024);}
            install(Root,Romfs,env,j.catalog,b,kernel,loader,p);
            j.outcome="Patch installed and verified. Reboot to Hekate, open More configs, then select FEXTendo Patch (emuMMC). The new kernel takes effect after reboot.";
        }
        j.status=inspect(Root,env,j.catalog,j.loaderKind);j.success=true;
        if(j.operation==Operation::Update&&!j.update.appAvailable) {
            if(j.status.installed)j.outcome="Your installed patch is up to date for this Atmosphere build.";
            else if(!j.status.supported)j.outcome="Update check completed. This release has no compatible patch for your Atmosphere build.";
        }
    } catch(const std::exception& e) {
        j.outcome=e.what();j.success=false;
        if((j.operation==Operation::UpdateApp||j.operation==Operation::PublishApp)&&!j.appPath.empty()){
            try{recoverAppUpdate(Root,j.appPath);}catch(const std::exception& recovery){j.outcome+=" Recovery: "+std::string(recovery.what());}
        }
        try{j.status=inspect(Root,runningEnvironment(),j.catalog,j.loaderKind);}catch(...){j.status.headline="Could not read SD card";j.status.detail=j.outcome;}
    } catch(...) {j.outcome="Operation failed. Keep the SD card connected and reopen FEXTendo Patch.";}
    j.done.store(true,std::memory_order_release);
}
bool start(Job& j,Operation op,const Catalog& catalog,const View& v,const std::string& loaderKind,const Update& update,const std::string& appPath) {
    j.operation=op;j.catalog=catalog;j.selected=v.status.bundle;j.repository=v.repository;j.loaderKind=loaderKind;
    j.update=update;j.appPath=appPath;
    j.outcome.clear();j.progress="Preparing...";j.updateText.clear();j.percent=0;j.success=false;j.done=false;j.cancel=false;
    Result r=threadCreate(&j.thread,worker,&j,nullptr,512*1024,0x2e,-2);
    if(R_FAILED(r))return false;
    if(R_FAILED(threadStart(&j.thread))){threadClose(&j.thread);return false;}return true;
}
}
int main(int argc,char** argv) {
    using namespace fxp;
    bool mounted=false, framebuffer=false, active=false;
    Framebuffer fb{};Job j;
    try {
        std::string appPath;
        const std::string launchArgument=argc>0&&argv&&argv[0]?argv[0]:"";
        try{appPath=appRelativePath(launchArgument);}catch(...){} // nxlink / embedded launches cannot self-update.
        if(!appPath.empty()){
            const bool recovered=recoverAppUpdate(Root,appPath);
            if(launchArgument.size()>=13&&launchArgument.compare(launchArgument.size()-13,13,".recovery.nro")==0)
                throw std::runtime_error(recovered?"App update recovered. Close this screen and open the normal FEXTendo Patch NRO.":"Open the normal FEXTendo Patch NRO to continue.");
        }
        require(R_SUCCEEDED(romfsInit()),"Could not open embedded resources. Recopy FEXTendo Patch.nro.");mounted=true;
        Ui ui(Romfs);Catalog catalog=loadCatalog(Romfs);View view;Update available;
        require(R_SUCCEEDED(framebufferCreate(&fb,nwindowGetDefault(),1280,720,PIXEL_FORMAT_RGBA_8888,2)),"Could not initialize display.");framebuffer=true;
        require(R_SUCCEEDED(framebufferMakeLinear(&fb)),"Could not allocate display buffer.");
        padConfigureInput(1,HidNpadStyleSet_NpadStandard);PadState pad;padInitializeAny(&pad);hidInitializeTouchScreen();
        bool previousTouch=false, running=true;std::string loaderKind="auto";
        auto launch=[&](Operation op){
            if(start(j,op,catalog,view,loaderKind,available,appPath)){active=true;view.busy=true;view.confirm=false;view.message=false;view.finishing=op==Operation::PublishApp;view.title=op==Operation::Update?"Checking for updates":op==Operation::UpdateApp?"Downloading app update":op==Operation::PublishApp?"Updating app":op==Operation::Install?"Installing patch":op==Operation::Recover?"Recovering installation":"Refreshing status";}
            else {view.message=true;view.title="Could not start";view.detail="Not enough resources to start the worker. Close and reopen the app.";view.success=false;}
        };
        auto confirmApp=[&]{view.message=false;view.confirm=true;view.appConfirm=true;view.title="Update app to v"+available.appVersion+"?";
            view.detail=std::string("Current app: v")+AppVersion+". Download and install FEXTendo Patch v"+available.appVersion+" from GitHub, then exit and reopen the app. Your boot patch and settings stay as they are.";};
        launch(Operation::Refresh);
        while(running && appletMainLoop()) {
            if(active&&j.done.load(std::memory_order_acquire)) {
                threadWaitForExit(&j.thread);threadClose(&j.thread);active=false;view.busy=false;
                catalog=j.catalog;view.status=j.status;view.repository=j.repository;
                if(j.operation==Operation::Update&&j.success){available=j.update;view.appUpdateAvailable=available.appAvailable;}
                if(!j.updateText.empty())view.updateText=j.updateText;
                else if(view.repository.empty())view.updateText="Source not configured - offline install available";
                if(j.operation!=Operation::Refresh||!j.success){view.message=true;view.success=j.success;view.title=j.success?"Completed":"Operation not completed";view.detail=j.outcome;}
                if(!view.status.ready&&!view.status.recovery)view.selection=1;
                if(j.operation==Operation::Update&&j.success&&available.appAvailable)confirmApp();
                if(j.operation==Operation::UpdateApp&&j.success){
                    // UI assets/catalog are already in RAM. Release the open NRO
                    // RomFS handle before renaming it, then require an app restart.
                    require(R_SUCCEEDED(romfsExit()),"Could not close app resources. Reopen to recover the staged update.");mounted=false;
                    view.exitRequired=true;launch(Operation::PublishApp);
                }
            }
            if(active){mutexLock(&j.lock);view.progress=j.progress;view.percent=j.percent;mutexUnlock(&j.lock);}
            padUpdate(&pad);u64 down=padGetButtonsDown(&pad);
            HidTouchScreenState touch{};hidGetTouchScreenStates(&touch,1);bool touched=touch.count>0;
            bool tap=touched&&!previousTouch;previousTouch=touched;
            bool accept=(down&HidNpadButton_A)!=0;
            if(view.busy){if(!view.finishing&&(down&HidNpadButton_B))j.cancel.store(true,std::memory_order_relaxed);}
            else if(view.exitRequired){if(down&(HidNpadButton_A|HidNpadButton_B|HidNpadButton_Plus)||tap)running=false;}
            else if(view.about){if(down&(HidNpadButton_B|HidNpadButton_A))view.about=false;}
            else if(view.message){if(down&(HidNpadButton_A|HidNpadButton_B)||tap)view.message=false;}
            else if(view.confirm){
                if(down&HidNpadButton_B)view.confirm=false;
                if(tap&&touch.touches[0].y>=507&&touch.touches[0].y<553){if(touch.touches[0].x>=279&&touch.touches[0].x<537)accept=true;else view.confirm=false;}
                if(accept)launch(view.appConfirm?Operation::UpdateApp:Operation::Install);
            }else{
                int choice=tap?Ui::loaderHit(touch.touches[0].x,touch.touches[0].y):-1;
                if(!view.status.recovery&&((down&HidNpadButton_Y)||choice>=0)){
                    loaderKind=choice>=0?(choice==0?"stock":"hoc"):(view.status.loaderKind=="stock"?"hoc":"stock");
                    launch(Operation::Refresh);
                }
                if(active){u32 stride=0;auto* pixels=static_cast<uint32_t*>(framebufferBegin(&fb,&stride));ui.draw(pixels,stride/4,view);framebufferEnd(&fb);continue;}
                if(down&(HidNpadButton_Right|HidNpadButton_StickLRight|HidNpadButton_Down|HidNpadButton_StickLDown))view.selection=(view.selection+1)%3;
                if(down&(HidNpadButton_Left|HidNpadButton_StickLLeft|HidNpadButton_Up|HidNpadButton_StickLUp))view.selection=(view.selection+2)%3;
                if(down&(HidNpadButton_Plus|HidNpadButton_B))running=false;
                if(down&HidNpadButton_X)view.about=true;
                if(tap){int hit=Ui::hit(touch.touches[0].x,touch.touches[0].y);if(hit>=0){view.selection=hit;accept=true;}}
                if(accept&&running&&!view.about){
                    if(view.selection==1){if(view.appUpdateAvailable)confirmApp();else launch(Operation::Update);}
                    else if(view.selection==2)launch(Operation::Refresh);
                    else if(view.status.recovery)launch(Operation::Recover);
                    else if(view.status.ready&&!view.status.installed){
                        view.confirm=true;view.appConfirm=false;view.title="Install FEXTendo Patch?";
                        const auto& b=view.status.bundle;
                        view.detail="Install patch v"+b.version+" for Atmosphere "+b.atmosphere+" using "+loaderLabel(b)+". ";
                        view.detail+=b.loaderKind=="stock"?"No HOC is installed; existing sys-clk settings are kept. ":"Uses official HOC defaults in this boot entry. ";
                        if(!view.status.revisionMatches)view.detail+="Source revision differs from the bundled build. ";
                        view.detail+="Adds or updates FEXTendo Patch (emuMMC). Reboot through Hekate to activate.";
                    }
                }
            }
            u32 stride=0;auto* pixels=static_cast<uint32_t*>(framebufferBegin(&fb,&stride));ui.draw(pixels,stride/4,view);framebufferEnd(&fb);
        }
    }catch(const std::exception& e){
        if(framebuffer){framebufferClose(&fb);framebuffer=false;}
        consoleInit(nullptr);printf("FEXTendo Patch\n\n%s\n\nPress + to close.\n",e.what());PadState pad;padConfigureInput(1,HidNpadStyleSet_NpadStandard);padInitializeAny(&pad);
        while(appletMainLoop()){padUpdate(&pad);if(padGetButtonsDown(&pad)&HidNpadButton_Plus)break;consoleUpdate(nullptr);}consoleExit(nullptr);
    }
    if(active){j.cancel=true;threadWaitForExit(&j.thread);threadClose(&j.thread);}
    if(framebuffer)framebufferClose(&fb);
    if(mounted)romfsExit();
    return 0;
}
