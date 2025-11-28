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

#include "mem/cache/replacement_policies/lvp_rp.hh"

#include <cassert>
#include <memory>

#include "params/LvPRP.hh"
#include "sim/cur_tick.hh"

namespace gem5
{

namespace replacement_policy
{

LvP::LvP(const Params &p)
  : Base(p),
    predictionTable(PT_ROWS, std::vector<PredictionTableEntry>(PT_COLS))
{
}

uint8_t
LvP::hashPC(Addr pc) const
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
LvP::hashAddress(Addr addr) const
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
LvP::incrementCounter(uint8_t &counter)
{
    if (counter < MAX_COUNTER) {
        counter++;
    }
}

bool
LvP::hasExpired(const LvPReplData* repl_data, bool is_mru) const
{
    // MRU blocks never expire
    if (is_mru) {
        return false;
    }

    // A block has expired if:
    // 1. Its event counter >= past maximum threshold
    // 2. Its confidence bit is set
    return repl_data->confidence &&
           (repl_data->eventCounter >= repl_data->maxCountPast);
}

void
LvP::invalidate(const std::shared_ptr<ReplacementData>& replacement_data)
{
    auto casted_replacement_data =
        std::static_pointer_cast<LvPReplData>(replacement_data);

    // Reset all fields
    casted_replacement_data->hashedPC = 0;
    casted_replacement_data->eventCounter = 0;
    casted_replacement_data->maxCountPast = 0;
    casted_replacement_data->confidence = false;
    casted_replacement_data->lastTouchTick = Tick(0);
}

void
LvP::touch(const std::shared_ptr<ReplacementData>& replacement_data,
    const PacketPtr pkt)
{
    auto casted_replacement_data =
        std::static_pointer_cast<LvPReplData>(replacement_data);

    // Step 1: On cache hit, increment only this block's counter
    incrementCounter(casted_replacement_data->eventCounter);

    // Update last touch tick for MRU detection
    casted_replacement_data->lastTouchTick = curTick();
}

void
LvP::touch(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    panic("LvP requires packet information for proper operation.");
}

void
LvP::reset(const std::shared_ptr<ReplacementData>& replacement_data,
    const PacketPtr pkt)
{
    auto casted_replacement_data =
        std::static_pointer_cast<LvPReplData>(replacement_data);

    // Step 2d: Place new block - initialize fields
    casted_replacement_data->eventCounter = 0;
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
LvP::reset(const std::shared_ptr<ReplacementData>& replacement_data) const
{
    panic("LvP requires packet information for proper operation.");
}

ReplaceableEntry*
LvP::getVictim(const ReplacementCandidates& candidates) const
{
    assert(candidates.size() > 0);

    // Find MRU block (highest lastTouchTick)
    Tick max_tick = 0;
    for (const auto& candidate : candidates) {
        auto repl_data = std::static_pointer_cast<LvPReplData>(
            candidate->replacementData);
        if (repl_data->lastTouchTick > max_tick) {
            max_tick = repl_data->lastTouchTick;
        }
    }

    // Step 2a & 2b: Find expired blocks and select closest to LRU
    ReplaceableEntry* victim = nullptr;
    Tick victim_tick = max_tick + 1;  // Initialize to value > any real tick

    for (const auto& candidate : candidates) {
        auto repl_data = std::static_pointer_cast<LvPReplData>(
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
            auto repl_data = std::static_pointer_cast<LvPReplData>(
                candidate->replacementData);
            auto victim_data = std::static_pointer_cast<LvPReplData>(
                victim->replacementData);

            if (repl_data->lastTouchTick < victim_data->lastTouchTick) {
                victim = candidate;
            }
        }
    }

    // Step 2c: Update prediction table with evicted block's information
    auto evicted_data = std::static_pointer_cast<LvPReplData>(
        victim->replacementData);

    // Update PT: store the evicted block's counter as new maxCountPast
    // Update confidence: set to true if counter equals previous maxCountPast
    // (indicating predictability)
    // Note: In a full implementation, we would need the address here.
    // This would typically be handled in the cache controller during eviction.

    return victim;
}

std::shared_ptr<ReplacementData>
LvP::instantiateEntry()
{
    return std::shared_ptr<ReplacementData>(new LvPReplData());
}

void
LvP::updateOnEviction(
    const std::shared_ptr<ReplacementData>& replacement_data,
    Addr addr)
{
    auto evicted = std::static_pointer_cast<LvPReplData>(replacement_data);

    // Index PT by stored hashedPC and hashed address of the evicted block
    uint8_t hashed_pc = evicted->hashedPC;
    uint8_t hashed_addr = hashAddress(addr);

    auto &pt_entry = predictionTable[hashed_pc][hashed_addr];
    const uint8_t old_past = pt_entry.maxCountPast;
    const uint8_t new_past = evicted->eventCounter;

    pt_entry.maxCountPast = new_past;
    pt_entry.confidence = (new_past == old_past);
}

} // namespace replacement_policy
} // namespace gem5
