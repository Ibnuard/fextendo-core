// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <functional>
#include <string>
#include <vector>
#include "json.hpp"

namespace fxp {
using Bytes = std::vector<uint8_t>;
using Json = nlohmann::json;
constexpr const char* AppVersion = "1.3.0";
constexpr const char* StateDir = "switch/fextendo-patch";
constexpr const char* EntryPath = "bootloader/ini/fextendo-patch.ini";
struct Asset { std::string name, hash, url; uint64_t size=0; };
struct Bundle {
    std::string version, atmosphere, revision, hoc, hos, loaderKind="hoc";
    Asset kernel, loader;
    bool online=false;
};
struct Catalog { std::string version; std::vector<Bundle> bundles; };
struct Environment { std::string atmosphere, hos; bool atmosphereKnown=false; };
struct Status {
    bool supported=false, ready=false, installed=false, recovery=false, revisionMatches=false;
    std::string running="Unknown", disk="Unknown", revision, hos="Unknown";
    std::string headline, detail, installation="Not installed", emummc="Not checked", loaderKind="stock";
    Bundle bundle;
};
struct Progress {
    std::function<void(const std::string&, int)> report;
    std::function<bool()> cancelled;
    void update(const std::string& text, int percent) const;
    void check() const;
};
void require(bool condition, const std::string& error);
std::string join(const std::string& root, const std::string& relative);
bool exists(const std::string& path);
Bytes read(const std::string& path, size_t limit);
std::string readText(const std::string& path, size_t limit=512*1024);
std::string hash(const Bytes& data);
bool matches(const std::string& path, uint64_t size, const std::string& sha);
Json parseJson(const std::string& text);
Catalog parseCatalog(const std::string& text);
Json bundleJson(const Bundle& bundle);
std::string bundleId(const Bundle& bundle);
int versionCompare(const std::string& a, const std::string& b);
Catalog loadCatalog(const std::string& romfs);
Status inspect(const std::string& root, const Environment& env, const Catalog& catalog,
               const std::string& loaderKind="auto");
std::string loaderLabel(const Bundle& bundle);
void mergeCatalog(Catalog& current, const Catalog& update);
bool pending(const std::string& root);
void recover(const std::string& root, const Progress& progress);
void install(const std::string& root, const std::string& romfs,
             const Environment& env, const Catalog& catalog, const Bundle& bundle,
             const Bytes& kernel, const Bytes& loader, const Progress& progress);
std::string readRepository(const std::string& root);
std::string bootEntry(const std::string& base, const Bundle& bundle);
// All mutations pass this hook. Host tests simulate termination at every boundary.
void mutationPoint();
}
