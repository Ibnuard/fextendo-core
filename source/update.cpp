// SPDX-License-Identifier: GPL-2.0-or-later
#include "update.hpp"
#include <curl/curl.h>
#include <algorithm>
#include <stdexcept>
#ifdef __SWITCH__
#include <switch.h>
#endif

namespace fxp {
static bool validRepo(const std::string& s) {
    auto slash=s.find('/');return slash>0&&slash<s.size()-1&&s.size()<140&&s.find('/',slash+1)==std::string::npos&&
        s.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/")==std::string::npos&&s.find("..")==std::string::npos;
}
std::vector<Asset> releaseAssets(const std::string& repo,const std::string& response,std::string& tag) {
    require(validRepo(repo),"Invalid repository.");auto j=parseJson(response);
    require(!j.at("draft").get<bool>()&&!j.at("prerelease").get<bool>(),"Only published stable releases are accepted.");
    tag=j.at("tag_name");require(!tag.empty()&&tag.size()<80,"Invalid release tag.");
    auto list=j.at("assets");require(list.is_array()&&list.size()<=128,"Invalid release asset list.");
    std::vector<Asset> out;
    for(const auto& item:list) {
        Asset a;a.name=item.at("name");a.url=item.at("browser_download_url");a.size=item.at("size");
        // Unrelated release assets (source archives, NRO) may have no digest.
        if(item.contains("digest")&&item["digest"].is_string()) {
            auto digest=item["digest"].get<std::string>();if(digest.compare(0,7,"sha256:")==0)a.hash=digest.substr(7);
        }
        require(std::none_of(out.begin(),out.end(),[&](auto& x){return x.name==a.name;}),"Duplicate release asset name.");
        const auto prefix="https://github.com/"+repo+"/releases/download/";
        require(a.url.compare(0,prefix.size(),prefix)==0&&a.url.size()<512&&a.url.find_first_of("\r\n\\?#") == std::string::npos,"Release asset URL is outside the configured repository.");
        out.push_back(a);
    }return out;
}
static Asset findAsset(const std::vector<Asset>& assets,const std::string& name) {
    auto it=std::find_if(assets.begin(),assets.end(),[&](auto& a){return a.name==name;});
    require(it!=assets.end(),"Release is missing "+name);
    require(it->hash.size()==64&&it->hash.find_first_not_of("0123456789abcdef")==std::string::npos,"GitHub has no SHA-256 digest for "+name+". Publish a new release asset.");
    return *it;
}
Catalog verifyReleaseCatalog(const Bytes& manifest,const std::vector<Asset>& assets) {
    const auto& a=findAsset(assets,"fextendo-patch.json");
    require(a.size==manifest.size()&&a.hash==hash(manifest),"Release catalog SHA-256 mismatch.");
    auto c=parseCatalog(std::string(manifest.begin(),manifest.end()));
    for(auto& b:c.bundles) {
        for(auto* target:{&b.kernel,&b.loader}) {
            const auto& asset=findAsset(assets,target->name);
            require(asset.hash==target->hash&&asset.size==target->size,"Release asset differs from catalog: "+target->name);
            target->url=asset.url;
        }b.online=true;
    }return c;
}
struct Network {
    bool socket=false, curl=false;
    Network() {
#ifdef __SWITCH__
        require(R_SUCCEEDED(socketInitializeDefault()),"Network service unavailable. Check your connection.");socket=true;
#endif
        if(curl_global_init(CURL_GLOBAL_DEFAULT)!=CURLE_OK) {
#ifdef __SWITCH__
            if(socket)socketExit();
#endif
            throw std::runtime_error("Could not initialize HTTPS.");
        }curl=true;
    }
    ~Network(){if(curl)curl_global_cleanup();
#ifdef __SWITCH__
        if(socket)socketExit();
#endif
    }
};
struct Transfer { Bytes data; size_t limit; const Progress* progress; };
static size_t receive(char* data,size_t size,size_t count,void* opaque) {
    auto& t=*static_cast<Transfer*>(opaque);
    if(size && count>t.limit/size)return 0;
    size_t n=size*count;if(n>t.limit-t.data.size())return 0;
    try {t.data.insert(t.data.end(),data,data+n);return n;}catch(...){return 0;}
}
static int advance(void* opaque,curl_off_t total,curl_off_t now,curl_off_t,curl_off_t) {
    auto& t=*static_cast<Transfer*>(opaque);
    if(t.progress->cancelled&&t.progress->cancelled())return 1;
    t.progress->update("Downloading and verifying from GitHub",total>0?int(std::min<curl_off_t>(now*100/total,100)):0);return 0;
}
static Bytes get(const std::string& url,size_t limit,const Progress& p) {
    require(url.compare(0,8,"https://")==0,"HTTPS is required.");p.check();
    CURL* curl=curl_easy_init();require(curl!=nullptr,"Could not create HTTPS request.");
    Transfer t{{},limit,&p};t.data.reserve(std::min<size_t>(limit,256*1024));
    auto* headers=curl_slist_append(nullptr,"Accept: application/vnd.github+json");
    headers=curl_slist_append(headers,"X-GitHub-Api-Version: 2022-11-28");
    curl_easy_setopt(curl,CURLOPT_URL,url.c_str());curl_easy_setopt(curl,CURLOPT_HTTPHEADER,headers);
    const auto userAgent=std::string("FEXTendo-Patch/")+AppVersion;
    curl_easy_setopt(curl,CURLOPT_USERAGENT,userAgent.c_str());
    curl_easy_setopt(curl,CURLOPT_PROTOCOLS,CURLPROTO_HTTPS);curl_easy_setopt(curl,CURLOPT_REDIR_PROTOCOLS,CURLPROTO_HTTPS);
    curl_easy_setopt(curl,CURLOPT_FOLLOWLOCATION,1L);curl_easy_setopt(curl,CURLOPT_MAXREDIRS,4L);
    curl_easy_setopt(curl,CURLOPT_SSL_VERIFYPEER,1L);curl_easy_setopt(curl,CURLOPT_SSL_VERIFYHOST,2L);
    curl_easy_setopt(curl,CURLOPT_SSLVERSION,CURL_SSLVERSION_TLSv1_2);curl_easy_setopt(curl,CURLOPT_FAILONERROR,1L);
    curl_easy_setopt(curl,CURLOPT_CONNECTTIMEOUT,20L);curl_easy_setopt(curl,CURLOPT_TIMEOUT,180L);
    curl_easy_setopt(curl,CURLOPT_LOW_SPEED_LIMIT,1024L);curl_easy_setopt(curl,CURLOPT_LOW_SPEED_TIME,25L);
    curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,receive);curl_easy_setopt(curl,CURLOPT_WRITEDATA,&t);
    curl_easy_setopt(curl,CURLOPT_XFERINFOFUNCTION,advance);curl_easy_setopt(curl,CURLOPT_XFERINFODATA,&t);curl_easy_setopt(curl,CURLOPT_NOPROGRESS,0L);
    auto code=curl_easy_perform(curl);long status=0;curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&status);
    curl_slist_free_all(headers);curl_easy_cleanup(curl);p.check();
    if(status==404)throw std::runtime_error("No public stable release found. Check repository and release visibility.");
    if(status==403||status==429)throw std::runtime_error("GitHub request limit reached or access denied. Try again later.");
    require(code==CURLE_OK&&status==200,"HTTPS download failed (HTTP "+std::to_string(status)+", "+curl_easy_strerror(code)+"). Check Wi-Fi and console date/time.");
    return std::move(t.data);
}
Bytes download(const Asset& a,const Progress& p) {
    require(a.size>0&&a.size<=16*1024*1024,"Invalid download size.");Network network;
    auto data=get(a.url,a.size,p);require(data.size()==a.size&&hash(data)==a.hash,"Downloaded asset SHA-256 mismatch. Boot files unchanged.");return data;
}
Update checkUpdate(const std::string& repo,const Progress& p) {
    require(!repo.empty(),"Update source is not configured. Set repository=owner/repo in switch/fextendo-patch/update.ini.");
    require(validRepo(repo),"Invalid update repository.");Network network;
    auto response=get("https://api.github.com/repos/"+repo+"/releases/latest",512*1024,p);
    Update u;auto assets=releaseAssets(repo,std::string(response.begin(),response.end()),u.tag);
    const auto& manifest=findAsset(assets,"fextendo-patch.json");require(manifest.size>0&&manifest.size<=512*1024,"Invalid catalog size.");
    auto data=get(manifest.url,manifest.size,p);u.catalog=verifyReleaseCatalog(data,assets);return u;
}
}
