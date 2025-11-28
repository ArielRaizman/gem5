/**
 * Copyright (c) 2025
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met: redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer;
 * redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution;
 * neither the name of the copyright holders nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "mem/cache/replacement_policies/aip_rp.hh"

#include <algorithm>
#include <cassert>
#include <memory>

#include "params/AIPRP.hh"
#include "sim/cur_tick.hh"

namespace gem5
{

namespace replacement_policy
{

AIP::AIP(const Params &p)
  : Base(p),
    predictionTable(PT_ROWS, std::vector<PredictionTableEntry>(PT_COLS))
{
}

uint8_t
AIP::hashPC(Addr pc) const
{
    // XOR-fold the PC to 8 bits for better distribution
    uint8_t hash = 0;
    Addr temp = pc;
    while (temp > 0) {
        hash ^= (temp & 0xFF);
        temp >>= 8;
    }
    return hash;
}

uint8_t
AIP::hashAddress(Addr addr) const
{
    // XOR-fold the address to 8 bits for better distribution
    uint8_t hash = 0;
    Addr temp = addr;
    while (temp > 0) {
        hash ^= (temp & 0xFF);
        temp >>= 8;
    }
    return hash;
}

void
AIP::incrementCounter(uint8_t &counter)
{
    if (counter < MAX_COUNTER) {
        counter++;
    }
}

bool
AIP::hasExpired(const AIPReplData* repl_data, bool is_mru) const
{
    // MRU blocks never expire
    if (is_mru) {
        return false;
    }

    // A block has expired if:
    // 1. Its event counter exceeds BOTH past and present maximums
    // 2. Its confidence bit is set
    return repl_data->confidence &&
           (repl_data->eventCounter > repl_data->maxCountPast) &&
           (repl_data->eventCounter > repl_data->maxCountPresent);
}

void
AIP::invalidate(const std::shared_ptr<ReplacementData>& replacement_data)
{
    auto casted_replacement_data =
        std::static_pointer_cast<AIPReplData>(replacement_data);

    // Reset all fields
    casted_replacement_data->hashedPC = 0;
    casted_replacement_data->eventCounter = 0;
    casted_replacement_data->maxCountPast = 0;
    casted_replacement_data->maxCountPresent = 0;
    casted_replacement_data->confidence = false;
    casted_replacement_data->lastTouchTick = Tick(0);
}

void
AIP::touch(const std::shared_ptr<ReplacementData>& replacement_data,
    const PacketPtr pkt)
{
    auto casted_replacement_data =
        std::static_pointer_cast<AIPReplData>(replacement_data);

    // Step 2: On cache hit, update present maximum and reset counter.
    // The access interval is the number of set accesses BETWEEN consecutive
    // hits to this line. Since notifySetAccess increments all counters on
    // every access (including this hit), subtract one to exclude the current
    // access from the completed interval.
    uint8_t completed_interval = casted_replacement_data->eventCounter;
    if (completed_interval > 0) {
        completed_interval -= 1;
    }
    casted_replacement_data->maxCountPresent = std::max(
        casted_replacement_data->maxCountPresent,
        completed_interval);

    // Reset event counter to start measuring next access interval
    casted_replacement_data->eventCounter = 0;

    // Update last touch tick for MRU detection
    casted_replacement_data->lastTouchTick = curTick();
}

void
AIP::touch(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    panic("AIP requires packet information for proper operation.");
}

void
AIP::reset(const std::shared_ptr<ReplacementData>& replacement_data,
    const PacketPtr pkt)
{
    auto casted_replacement_data =
        std::static_pointer_cast<AIPReplData>(replacement_data);

    // Step 3d: Place new block - initialize fields
    casted_replacement_data->eventCounter = 0;
    casted_replacement_data->maxCountPresent = 0;
    casted_replacement_data->lastTouchTick = curTick();

    // Get PC and address for prediction table lookup
    uint8_t hashed_pc = 0;
    if (pkt->req->hasPC()) {
        hashed_pc = hashPC(pkt->req->getPC());
    }
    casted_replacement_data->hashedPC = hashed_pc;

    uint8_t hashed_addr = hashAddress(pkt->getAddr());

    // Copy maxCountPast and confidence from prediction table
    const auto& pt_entry = predictionTable[hashed_pc][hashed_addr];
    casted_replacement_data->maxCountPast = pt_entry.maxCountPast;
    casted_replacement_data->confidence = pt_entry.confidence;
}

void
AIP::reset(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    panic("AIP requires packet information for proper operation.");
}

ReplaceableEntry*
AIP::getVictim(const ReplacementCandidates& candidates) const
{
    assert(candidates.size() > 0);

    // Find MRU block (highest lastTouchTick)
    Tick max_tick = 0;
    for (const auto& candidate : candidates) {
        auto repl_data = std::static_pointer_cast<AIPReplData>(
            candidate->replacementData);
        if (repl_data->lastTouchTick > max_tick) {
            max_tick = repl_data->lastTouchTick;
        }
    }

    // Step 3a & 3b: Find expired blocks and select closest to LRU
    ReplaceableEntry* victim = nullptr;
    Tick victim_tick = max_tick + 1;  // Initialize to value > any real tick

    for (const auto& candidate : candidates) {
        auto repl_data = std::static_pointer_cast<AIPReplData>(
            candidate->replacementData);

        bool is_mru = (repl_data->lastTouchTick == max_tick);

        if (hasExpired(repl_data.get(), is_mru)) {
            // Among expired blocks, choose the one closest to LRU
            // (lowest lastTouchTick)
            if (repl_data->lastTouchTick < victim_tick) {
                victim = candidate;
                victim_tick = repl_data->lastTouchTick;
            }
        }
    }

    // If no block expired, fall back to traditional LRU
    if (victim == nullptr) {
        victim = candidates[0];
        for (const auto& candidate : candidates) {
            auto repl_data = std::static_pointer_cast<AIPReplData>(
                candidate->replacementData);
            auto victim_data = std::static_pointer_cast<AIPReplData>(
                victim->replacementData);

            if (repl_data->lastTouchTick < victim_data->lastTouchTick) {
                victim = candidate;
            }
        }
    }

    // Step 3c: Update prediction table with evicted block's information
    auto evicted_data = std::static_pointer_cast<AIPReplData>(
        victim->replacementData);

    // Note: We can't easily get the address here, so we'll need to handle
    // this during the actual eviction. For now, we update based on stored PC.
    // In a real implementation, this would be done in the cache controller.

    return victim;
}

void
AIP::notifySetAccess(const ReplacementCandidates& candidates)
{
    // Step 1: Increment event counter for all blocks in the set
    for (const auto& candidate : candidates) {
        auto repl_data = std::static_pointer_cast<AIPReplData>(
            candidate->replacementData);
        incrementCounter(repl_data->eventCounter);
    }
}

std::shared_ptr<ReplacementData>
AIP::instantiateEntry()
{
    return std::shared_ptr<ReplacementData>(new AIPReplData());
}

void
AIP::updateOnEviction(
    const std::shared_ptr<ReplacementData>& replacement_data,
    Addr addr)
{
    auto evicted = std::static_pointer_cast<AIPReplData>(replacement_data);

    // Index PT by stored hashedPC and hashed address of the evicted block
    uint8_t hashed_pc = evicted->hashedPC;
    uint8_t hashed_addr = hashAddress(addr);

    auto &pt_entry = predictionTable[hashed_pc][hashed_addr];
    const uint8_t old_past = pt_entry.maxCountPast;
    const uint8_t new_past = evicted->maxCountPresent;

    pt_entry.maxCountPast = new_past;
    pt_entry.confidence = (new_past == old_past);
}

} // namespace replacement_policy
} // namespace gem5
