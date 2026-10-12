// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "core.hpp"
namespace fxp {
constexpr size_t MaxNroSize=32*1024*1024;
struct Update {
    Catalog catalog;
    std::string tag, appVersion;
    Asset app;
    bool hasCatalog=false, appAvailable=false, appRequired=false;
};
// Separate parsing from transport so release fixtures exercise the production validator.
std::vector<Asset> releaseAssets(const std::string& repository, const std::string& response, std::string& tag);
Catalog verifyReleaseCatalog(const Bytes& manifest, const std::vector<Asset>& assets);
Update verifyUpdate(const Bytes& manifest, const std::vector<Asset>& assets, const std::string& tag);
Bytes download(const Asset& asset, const Progress& progress);
Update checkUpdate(const std::string& repository, const Progress& progress);
// The launch argument identifies the actual installed NRO; never guess a target.
std::string appRelativePath(const std::string& launchArgument);
std::string nroVersion(const Bytes& data);
void stageAppUpdate(const std::string& root, const std::string& relative,
                    const std::string& version, const Asset& asset, const Bytes& data, const Progress& progress);
// The caller must unmount RomFS before publication or recovery.
void publishAppUpdate(const std::string& root, const std::string& relative, const Progress& progress);
bool recoverAppUpdate(const std::string& root, const std::string& relative);
}
