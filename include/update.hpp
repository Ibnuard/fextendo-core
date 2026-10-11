// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "core.hpp"
namespace fxp {
struct Update { Catalog catalog; std::string tag; };
// Separate parsing from transport so release fixtures exercise the production validator.
std::vector<Asset> releaseAssets(const std::string& repository, const std::string& response, std::string& tag);
Catalog verifyReleaseCatalog(const Bytes& manifest, const std::vector<Asset>& assets);
Bytes download(const Asset& asset, const Progress& progress);
Update checkUpdate(const std::string& repository, const Progress& progress);
}
