// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "core.hpp"
namespace fxp {
// Checked, durable SD operations shared by boot and NRO transactions.
void writeFile(const std::string& path, const Bytes& data);
void moveFile(const std::string& from, const std::string& to);
void removeFile(const std::string& path);
}
