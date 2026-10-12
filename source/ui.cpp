// SPDX-License-Identifier: GPL-2.0-or-later
// Glyph format compatible with the FEXTendo launcher (Inter, SIL OFL 1.1).
#include "ui.hpp"
#include <algorithm>
#include <cmath>
#include <sstream>
namespace fxp {
static constexpr uint32_t rgb(unsigned r,unsigned g,unsigned b){return r|(g<<8)|(b<<16)|0xff000000u;}
static constexpr auto White=rgb(241,246,251),Muted=rgb(156,174,194),Blue=rgb(66,155,255),Green=rgb(95,223,174),Amber=rgb(255,194,99);
static unsigned u16(const uint8_t* p){return p[0]|unsigned(p[1])<<8;}
static unsigned u32(const uint8_t* p){return u16(p)|u16(p+2)<<16;}
Ui::Ui(const std::string& romfs) {
    font=read(join(romfs,"ui/font.bin"),1024*1024);
    require(font.size()>=6088 && std::string(font.begin(),font.begin()+4)=="FXF2"&&u32(font.data()+4)==font.size()-6088,"Invalid UI font.");
    for(int i=0;i<380;i++){const uint8_t* g=font.data()+8+i*16;unsigned off=u32(g),w=u16(g+8),h=u16(g+10);require(w<128&&h<128&&off<=font.size()-6088&&w*h<=font.size()-6088-off,"Invalid font glyph.");}
    gamepad=read(join(romfs,"ui/gamepad.rgba"),88*64*4);wordmark=read(join(romfs,"ui/wordmark.rgba"),260*68*4);
    require(gamepad.size()==88*64*4&&wordmark.size()==260*68*4,"Invalid UI artwork.");
}
void Ui::pixel(int x,int y,uint32_t c,unsigned a) {
    if(x<0||y<0||x>=1280||y>=720||!a)return;
    auto& d=pixels[y*stride+x];
    if(a==255){d=c;return;}
    unsigned r=((d&255)*(255-a)+(c&255)*a+127)/255;
    unsigned g=(((d>>8)&255)*(255-a)+((c>>8)&255)*a+127)/255;
    unsigned b=(((d>>16)&255)*(255-a)+((c>>16)&255)*a+127)/255;d=rgb(r,g,b);
}
void Ui::rect(int x,int y,int w,int h,uint32_t c,unsigned a){for(int j=std::max(0,y);j<std::min(720,y+h);j++)for(int i=std::max(0,x);i<std::min(1280,x+w);i++)pixel(i,j,c,a);}
void Ui::round(int x,int y,int w,int h,int r,uint32_t c) {
    for(int j=0;j<h;j++)for(int i=0;i<w;i++) {
        float dx=std::max(float(r)-i-.5f,i+.5f-(w-r));float dy=std::max(float(r)-j-.5f,j+.5f-(h-r));
        if(dx<=0||dy<=0)pixel(x+i,y+j,c);
        else {float a=std::clamp(r+.5f-std::sqrt(dx*dx+dy*dy),0.f,1.f);pixel(x+i,y+j,c,unsigned(a*255));}
    }
}
int Ui::width(const std::string& s,int face) const {int result=0;for(unsigned char c:s){if(c<32||c>126)c='?';result+=u16(font.data()+8+(face*95+c-32)*16+12);}return result;}
void Ui::text(int x,int y,const std::string& s,int face,uint32_t color) {
    static int size[]={18,24,40,14};
    for(unsigned char c:s){if(c<32||c>126)c='?';auto* g=font.data()+8+(face*95+c-32)*16;
        int bx=int16_t(u16(g+4)),by=int16_t(u16(g+6)),w=u16(g+8),h=u16(g+10);auto* mask=font.data()+6088+u32(g);
        for(int yy=0;yy<h;yy++) {
            for(int xx=0;xx<w;xx++)pixel(x+bx+xx,y+size[face]+by+yy,color,mask[yy*w+xx]);
        }
        x+=u16(g+12);
    }
}
void Ui::wrapped(int x,int y,int w,const std::string& s,int face,uint32_t c,int lines) {
    std::istringstream words(s);std::string word,line;int count=0,step=face==1?34:27;
    while(words>>word){auto next=line.empty()?word:line+" "+word;
        if(width(next,face)>w&&!line.empty()){text(x,y+count*step,line,face,c);line=word;if(++count>=lines)return;}
        else line=next;
        // Long paths are split at character boundaries instead of overflowing a dialog.
        while(width(line,face)>w){size_t n=line.size();while(n&&width(line.substr(0,n),face)>w)n--;if(!n)break;text(x,y+count*step,line.substr(0,n),face,c);line.erase(0,n);if(++count>=lines)return;}
    }if(!line.empty()&&count<lines)text(x,y+count*step,line,face,c);
}
void Ui::image(int x,int y,int w,int h,const Bytes& b){for(int j=0;j<h;j++)for(int i=0;i<w;i++){auto* p=b.data()+(j*w+i)*4;pixel(x+i,y+j,rgb(p[0],p[1],p[2]),p[3]);}}
int Ui::hit(int x,int y){if(y>=548&&y<616){if(x>=60&&x<442)return 0;if(x>=458&&x<840)return 1;if(x>=856&&x<1220)return 2;}return -1;}
int Ui::loaderHit(int x,int y){if(y>=444&&y<503){if(x>=60&&x<420)return 0;if(x>=438&&x<798)return 1;}return -1;}
void Ui::draw(uint32_t* buffer,int pitch,const View& v) {
    pixels=buffer;stride=pitch;
    rect(0,0,1280,720,rgb(9,16,26));rect(0,0,1280,112,rgb(12,22,35));
    image(47,22,88,64,gamepad);image(145,20,260,68,wordmark);
    rect(432,36,1,43,rgb(51,65,83));text(458,40,"PATCH",1,White);
    text(1080,34,"MEMORY TOOLS",3,Muted);text(1160,57,std::string("v")+AppVersion,3,White);
    text(60,140,"SYSTEM STATUS",3,Muted);
    uint32_t accent=v.status.ready?Green:Amber;
    round(60,174,738,224,18,rgb(19,32,46));rect(60,198,4,170,accent);
    round(87,200,116,28,14,v.status.ready?rgb(24,66,55):rgb(67,49,30));
    text(101,206,v.status.ready?"COMPATIBLE":"ATTENTION",3,accent);
    text(86,244,v.status.headline.empty()?"Reading system...":v.status.headline,2,White);
    wrapped(87,307,672,v.status.detail,0,Muted,3);
    round(820,174,400,336,18,rgb(16,27,40));
    text(846,198,"YOUR CONSOLE",3,Muted);
    auto row=[&](int y,const std::string& k,const std::string& value){text(846,y,k,0,Muted);std::string shortValue=value;if(width(shortValue,0)>184)shortValue=shortValue.substr(0,17)+"...";text(1192-width(shortValue,0),y,shortValue,0,White);};
    row(239,"Atmosphere",v.status.running);row(271,"On SD",v.status.disk);row(303,"Revision",v.status.revision.empty()?"Unknown":v.status.revision);row(335,"System",v.status.hos);row(367,"emuMMC",v.status.emummc);
    rect(846,410,348,1,rgb(42,56,74));text(846,426,"PATCH / INSTALLATION",3,Muted);
    text(846,452,v.status.supported?"v"+v.status.bundle.version+" / "+(v.status.loaderKind=="stock"?"Standard":"HOC"):"No matching bundle",1,White);
    text(846,485,v.status.installation,3,Muted);
    text(60,416,"LOADER",3,Muted);text(612,416,"Y  Change loader",3,Muted);
    for(int i=0;i<2;i++){
        int x=i==0?60:438;bool selected=(v.status.loaderKind=="stock")== (i==0);
        round(x,444,360,59,10,selected?Blue:rgb(30,44,61));
        text(x+20,459,i==0?"Standard / sys-clk":"HOC / official defaults",0,White);
    }
    text(60,517,"Reboot through Hekate after installing.",3,Muted);
    std::string labels[]={v.status.recovery?"Recover installation":v.status.installed?"Already installed":"Install patch",v.appUpdateAvailable?"Update app":"Check update","Refresh status"};
    for(int i=0;i<3;i++){
        int x=i==0?60:i==1?458:856,w=i==2?364:382;
        bool disabled=i==0&&!v.status.recovery&&(!v.status.ready||v.status.installed);
        bool selected=i==v.selection;
        round(x,548,w,68,12,selected?Blue:rgb(30,44,61));
        if(selected)round(x+2,550,w-4,64,10,disabled?rgb(31,43,57):rgb(26,63,102));
        text(x+24,569,labels[i],1,disabled?Muted:White);
        if(selected)text(x+w-43,570,"A",0,disabled?Muted:Blue);
    }
    text(60,644,"UPDATE",3,Muted);wrapped(135,638,880,v.updateText,0,Muted,1);
    rect(0,680,1280,1,rgb(31,44,61));text(60,695,"A  Select     B  Back     +  Exit",3,Muted);text(1067,695,"X  About / help",3,Muted);
    if(v.confirm||v.message||v.busy||v.about){
        rect(0,0,1280,720,rgb(0,5,12),204);round(240,155,800,420,22,rgb(21,34,50));
        text(280,194,v.about?"FEXTendo Patch":v.title,1,White);
        rect(280,237,720,1,rgb(50,65,84));
        if(v.about){
            wrapped(280,258,716,"Kernel and loader patches are matched to the Atmosphere version and verified with SHA-256. Standard works without HOC; existing sys-clk settings are kept. HOC is optional and uses official defaults.",0,Muted,4);
            wrapped(280,378,716,"After installing, reboot to Hekate > More configs > FEXTendo Patch (emuMMC). Existing boot configurations and game folders stay separate.",0,Muted,3);
            text(280,486,"Credits: Atmosphere / HOC / libnx / FEXTendo",3,Muted);
            text(280,532,"B  Close",0,White);
        }else if(v.busy){
            wrapped(280,266,716,v.progress,0,White,4);round(280,400,720,10,5,rgb(43,57,75));
            if(v.percent>0)round(280,400,std::max(12,720*v.percent/100),10,5,Blue);
            text(280,453,"Keep the SD card connected until this operation finishes.",0,Muted);
            text(280,532,v.finishing?"Finishing update - keep the app open":"B  Cancel before changes are committed",0,White);
        }else{
            wrapped(280,264,716,v.detail,0,Muted,8);
            if(v.confirm){round(279,507,258,46,10,rgb(26,78,130));text(298,518,v.appConfirm?"A  Update app":"A  Install patch",0,White);text(582,518,"B  Cancel",0,Muted);}
            else text(280,532,v.exitRequired?"A  Exit app":"A / B  Close",0,v.success?Green:White);
        }
    }
}
}
