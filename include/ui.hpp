// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "core.hpp"
namespace fxp {
struct View {
    Status status;
    int selection=0, percent=0;
    bool busy=false, confirm=false, message=false, success=false, about=false;
    bool appUpdateAvailable=false, appConfirm=false, exitRequired=false, finishing=false;
    std::string repository, updateText="Bundled patch available offline";
    std::string title, detail, progress;
};
class Ui {
    Bytes font, gamepad, wordmark;
    uint32_t* pixels=nullptr;
    int stride=1280;
    void pixel(int x,int y,uint32_t color,unsigned alpha=255);
    void rect(int x,int y,int w,int h,uint32_t color,unsigned alpha=255);
    void round(int x,int y,int w,int h,int radius,uint32_t color);
    void text(int x,int y,const std::string& value,int font,uint32_t color);
    int width(const std::string& value,int face) const;
    void wrapped(int x,int y,int w,const std::string& value,int face,uint32_t color,int lines);
    void image(int x,int y,int w,int h,const Bytes& data);
public:
    explicit Ui(const std::string& romfs);
    void draw(uint32_t* pixels,int stride,const View& view);
    static int hit(int x,int y);
    static int loaderHit(int x,int y);
};
}
