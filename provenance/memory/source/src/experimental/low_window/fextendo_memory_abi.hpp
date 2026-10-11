/* SPDX-License-Identifier: MIT
 * FEXTendo experimental ABI v1. Private to the pinned kernel/loader pair.
 * This is NOT an upstream Atmosphere NPDM flag or a user configuration option.
 */
#pragma once
#include <cstddef>
#include <cstdint>

namespace ams::svc::fextendo {
    constexpr std::uint32_t RequestFlag = UINT32_C(1) << 30;
    constexpr std::uint64_t NativeStart = UINT64_C(0x100000000);
    constexpr std::size_t DescriptorSize = 32;

    constexpr std::uint32_t Read32(const unsigned char *p) {
        return std::uint32_t(p[0]) | (std::uint32_t(p[1]) << 8) |
               (std::uint32_t(p[2]) << 16) | (std::uint32_t(p[3]) << 24);
    }

    /* Fixed-size, little-endian ExeFS /fxtmem. Reject unknown extensions rather
     * than guessing: all reserved bytes must be zero in version 1. */
    constexpr bool ValidDescriptor(const unsigned char *p, std::size_t size) {
        if (p == nullptr || size != DescriptorSize) return false;
        constexpr unsigned char magic[8] = {'F','X','T','M','E','M',0,0};
        for (std::size_t i = 0; i < 8; ++i) if (p[i] != magic[i]) return false;
        if (Read32(p + 8) != 1 || Read32(p + 12) != DescriptorSize ||
            Read32(p + 16) != 1 || Read32(p + 20) != 0) return false;
        for (std::size_t i = 24; i < DescriptorSize; ++i) if (p[i]) return false;
        return true;
    }

    /* ARM64 + 39-bit + application pool only. Constants are checked against the
     * actual pinned svc enum by static_asserts in the patched shared header. */
    constexpr bool CompatibleFlags(std::uint32_t flags) {
        return (flags & 0x0f) == 0x07 && (flags & 0x40) &&
               !(flags & (0x780 | 0x2000));
    }
    constexpr bool Requested(std::uint32_t flags) { return (flags & RequestFlag) != 0; }
}
