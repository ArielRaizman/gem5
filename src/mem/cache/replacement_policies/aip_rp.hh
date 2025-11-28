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

/**
 * @file
 * Declaration of the Access Interval Predictor (AIP) replacement policy.
 *
 * The AIP algorithm counts the number of accesses to the set where the line
 * resides, between consecutive accesses to the line itself. It uses a
 * counter-based prediction mechanism with a 40KB prediction table to learn
 * access patterns and predict when cache lines should be evicted.
 *
 * Reference: "Counter-Based Cache Replacement Algorithms"
 */

#ifndef __MEM_CACHE_REPLACEMENT_POLICIES_AIP_RP_HH__
#define __MEM_CACHE_REPLACEMENT_POLICIES_AIP_RP_HH__

#include <cstdint>
#include <vector>

#include "mem/cache/replacement_policies/base.hh"
#include "mem/packet.hh"

namespace gem5
{

struct AIPRPParams;

namespace replacement_policy
{

class AIP : public Base
{
  protected:
    /** AIP-specific implementation of replacement data. */
    struct AIPReplData : ReplacementData
    {
        /** Hashed PC of the instruction that caused the miss (8 bits). */
        uint8_t hashedPC;

        /** Event counter: tracks accesses per set (4-bit saturating). */
        uint8_t eventCounter;

        /** Maximum event count from the past generation (4 bits). */
        uint8_t maxCountPast;

        /** Maximum event count in the current generation (4 bits). */
        uint8_t maxCountPresent;

        /** Confidence bit: indicates prediction confidence. */
        bool confidence;

        /** Last touch tick for MRU detection. */
        Tick lastTouchTick;

        /** Default constructor. */
        AIPReplData()
          : hashedPC(0), eventCounter(0), maxCountPast(0),
            maxCountPresent(0), confidence(false), lastTouchTick(0)
        {}
    };

    /** Prediction Table structure (256x256 = 40KB with 4-bit entries). */
    struct PredictionTableEntry
    {
        uint8_t maxCountPast;  // 4-bit threshold value
        bool confidence;       // 1-bit confidence

        PredictionTableEntry() : maxCountPast(0), confidence(false) {}
    };

    /** 256x256 Prediction Table (40KB). */
    std::vector<std::vector<PredictionTableEntry>> predictionTable;

    /** Maximum value for 4-bit saturating counter. */
    static constexpr uint8_t MAX_COUNTER = 15;

    /** PT dimensions. */
    static constexpr size_t PT_ROWS = 256;
    static constexpr size_t PT_COLS = 256;

    /**
     * Hash a PC value to 8 bits.
     *
     * @param pc The program counter value.
     * @return 8-bit hash of the PC.
     */
    uint8_t hashPC(Addr pc) const;

    /**
     * Hash a line address to 8 bits.
     *
     * @param addr The cache line address.
     * @return 8-bit hash of the address.
     */
    uint8_t hashAddress(Addr addr) const;

    /**
     * Increment a 4-bit saturating counter.
     *
     * @param counter Reference to the counter to increment.
     */
    void incrementCounter(uint8_t &counter);

    /**
     * Check if a block has expired based on AIP criteria.
     *
     * @param repl_data The replacement data to check.
     * @param is_mru Whether this block is the MRU block.
     * @return True if the block has expired.
     */
    bool hasExpired(const AIPReplData* repl_data, bool is_mru) const;

  public:
    typedef AIPRPParams Params;
    AIP(const Params &p);
    ~AIP() = default;

    /**
     * Invalidate replacement data to set it as the next probable victim.
     *
     * @param replacement_data Replacement data to be invalidated.
     */
    void invalidate(const std::shared_ptr<ReplacementData>& replacement_data)
                                                                    override;

    /**
     * Touch an entry to update its replacement data.
     * For AIP, this increments counters for all blocks in the set,
     * and resets the touched block's counter.
     *
     * @param replacement_data Replacement data to be touched.
     * @param pkt Packet that generated this access.
     */
    void touch(const std::shared_ptr<ReplacementData>& replacement_data,
        const PacketPtr pkt) override;
    void touch(const std::shared_ptr<ReplacementData>& replacement_data) const
        override;

    /**
     * Reset replacement data. Used when an entry is inserted.
     *
     * @param replacement_data Replacement data to be reset.
     * @param pkt Packet that generated this miss.
     */
    void reset(const std::shared_ptr<ReplacementData>& replacement_data,
        const PacketPtr pkt) override;
    void reset(const std::shared_ptr<ReplacementData>& replacement_data) const
        override;

    /**
     * Find replacement victim using AIP algorithm.
     * Selects expired blocks based on counter thresholds, or falls back to
     * LRU if no block has expired.
     *
     * @param candidates Replacement candidates, selected by indexing policy.
     * @return Replacement entry to be replaced.
     */
    ReplaceableEntry* getVictim(const ReplacementCandidates& candidates) const
                                                                     override;

    /**
     * Instantiate a replacement data entry.
     *
     * @return A shared pointer to the new replacement data.
     */
    std::shared_ptr<ReplacementData> instantiateEntry() override;

    /**
     * Notify policy about set access to increment all counters in the set.
     * This should be called for any access (hit or miss) to the set.
     *
     * @param candidates All entries in the accessed set.
     */
    void notifySetAccess(const ReplacementCandidates& candidates);

        /**
         * Update the prediction table on eviction of a block.
         * Stores the block's present maximum as the new past maximum and
         * updates the confidence based on stability.
         *
         * @param replacement_data Evicted block's replacement data.
         * @param addr The evicted block's address for hashing.
         */
        void updateOnEviction(
            const std::shared_ptr<ReplacementData>& replacement_data,
            Addr addr);
};

} // namespace replacement_policy
} // namespace gem5

#endif // __MEM_CACHE_REPLACEMENT_POLICIES_AIP_RP_HH__
