---

## 10. Supply, price and the economics

### 10.1 What a chip costs to build

![Build cost composition and implied margins](figures/fig16_bom.png)

No vendor discloses per-part cost of goods. The estimates below descend from the 2023 Raymond James H100 teardown, extended by Epoch AI, TrendForce and SemiAnalysis; the H100 row has been independently reproduced several times, the Blackwell rows are weaker. (all estimate)

| Chip | Logic die | HBM | CoWoS packaging | Substrate/test/assembly | Total build | Modelled sell | Implied margin |
|---|---|---|---|---|---|---|---|
| H100 SXM5 | $300 | **$1,350** | $750 | $920 | $3,320 | $28,000 | ~88% |
| H200 SXM5 | $300 | $1,500 | $750 | $1,700 | $4,250 | $38,000 | ~89% |
| B200 | $850 | **$2,900** | $1,100 | $1,550 | $6,400 | $40,000 | ~84% |
| GB200 superchip | $1,700 | $5,800 | $2,200 | $3,800 | $13,500 | $65,000 | ~79% |
| MI300X | $600 | $2,900 | $1,500 | $300 | $5,300 | $15,000 | ~65% |
| Gaudi 3 | $1,500 | $1,950 | $1,200 | $1,350 | $6,000 | $15,625 | ~62% |

HBM's share of build cost went from ~14% on A100 to 33–41% on H100 to ~45% on MI300X. On a B200 the memory costs roughly 3.4× the logic silicon.

The 84–88% implied per-die margins are not inconsistent with NVIDIA's **confirmed 74.9% corporate gross margin**, because rack-scale products bundle Grace CPUs, NVSwitches, ConnectX NICs, cabling and cold plates at lower margin, and because the model excludes R&D amortisation — Jensen Huang has put the NV-HBI die-to-die interconnect alone at about $10B of development.

Wafer prices, for the same reason people ask: N7 ~$10k, N5 ~$17k, N3 ~$21.5k in 2026, N2 ~$30k (though TrendForce argues the real N2-versus-N3 premium is 10–20%, not 50%), A16 ~$45k. A fully processed CoWoS wafer runs $10–12k with the interposer alone at 50–70% of packaging cost. (estimate)

### 10.2 The two real chokepoints

![CoWoS capacity, HBM share and HBM pricing](figures/fig17_supply.png)

**Advanced packaging.** TSMC CoWoS capacity: ~37.5k wafers/month in 2024, ~75k in 2025, a 120–140k target for 2026, with a further >60% expansion planned for 2027 and another 50–60k from OSAT partners. Against that, annual CoWoS demand went ~370k wafers (2024) → ~670k (2025) → approaching 1M (2026). The supply-demand gap is around 20%, forecast to narrow to about 10% by end-2026. NVIDIA reportedly reserved 800–850k wafers of 2026 capacity, over half the total; a competing estimate says ~60%, with the top three customers taking >85%. CoWoS lead times were 40–52 weeks in early 2026. (estimate; the allocation figures are channel checks that disagree)

Why this gates supply: a ~2,500 mm² H100-class interposer yields roughly 16–20 good packages per 300 mm wafer at 60–70% yield, so wafers per month converts almost directly into GPUs per month. **H100 availability through 2024 was constrained by packaging, not by logic wafers.**

**HBM.** All three suppliers sold out their 2026 capacity under multi-year agreements; as one analysis puts it, the market "is not price-discovered; it is administratively allocated." All three shipped HBM4 in volume during H1 2026. The only hard public number is Micron's disclosed **>$1B of HBM4 revenue**, with 12-high HBM4 ramping twice as fast as HBM3E did. Reported segment operating margins: Micron 80.4%, SK hynix 76.3%, Samsung DS 70.0%. Share estimates disagree materially between sources (SK hynix somewhere between 50% and 70% of NVIDIA's HBM4 allocation) because **no supplier reports HBM revenue separately**. HBM4 12-Hi 36 GB stacks are estimated at $500–600 against ~$300 for HBM3E, a 55–70% increase. (confirmed where noted; shares are estimates)

**And increasingly, electricity.** A GB200 NVL72 rack is 132 kW, a GB300 about 140 kW, an AMD Helios 125–135 kW, and a TPU v7 superpod nearly 10 MW. The GB200 chassis weighs about 1.36 tonnes and does not fit through a standard datacenter door — retrofits are frequently impossible. Transformer lead times exceed 50 weeks. Stargate Abilene has 421 MW of IT load energised of a 1.2 GW design, and a 600 MW tranche was scrapped in March 2026 on financing and demand-forecast changes. Big-four 2026 capex guidance totals about **$630B, up 62%** year over year. (confirmed for capex guidance and rack power; site details are estimates)

### 10.3 What it costs to rent

![Cloud price per chip-hour across providers and tiers](figures/fig14_cloud_prices.png)

<!-- TABLE:cloud_prices -->

The dominant fact here is dispersion, not level. Identical H100 silicon spans **$0.27 (Vast.ai spot) to $12.29 (Azure on-demand)** — a 45× spread, or 12× excluding spot. MI300X spans $1.45 to $7.86. Three structural reasons: neocloud overhead is roughly $0.20–0.50 per GPU-hour against $1.00–2.00 at hyperscalers; marketplaces expose host-set prices with no SLA; and hyperscaler list prices bundle support, networking, storage and compliance that specialists do not.

**The trend is not monotonic, and most published narratives are out of date.** H100 on-demand went from roughly $7–10/hour at the 2023 peak to $2–4 by late 2025 — driven by CoWoS capacity doubling, neocloud entry, Blackwell pushing Hopper down the stack, and depreciation pressure on unsold inventory. Then it partially reversed: **contract pricing rose about 40% between October 2025 and March 2026, attributed to HBM3e cost pass-through.** Memory, not GPU fabrication, became the binding constraint. Blackwell lead times stretched to 3–7 months by early 2026. (estimate)

### 10.4 Normalised: what you get per dollar

![Price per PFLOP-hour and per TB/s-hour](figures/fig15_price_per_flop.png)

<!-- TABLE:price_per_flop -->

Two conclusions survive normalisation.

**Procurement channel dominates architecture.** An H100 on a marketplace beats a B200 on a hyperscaler per dense FP8 PFLOP-hour. For any buyer below reserved-capacity scale, *where* you buy matters more than *what* you buy.

**The TPU answer depends entirely on which price you are offered.** Ironwood at the $12.00 list price is $2.60 per dense FP8 PFLOP-hour — unremarkable. At the $5.40 three-year rate it is $1.17. At SemiAnalysis's estimated Anthropic rate of $1.60 it is $0.35, the cheapest compute in the table by a factor of three. That 7.5× spread is the single largest pricing asymmetry in the industry.

For decode-bound serving, use the memory-bandwidth column instead: dollars per TB/s-hour reorders the table and is a better proxy for tokens per second per user.

### 10.5 Total cost of ownership

Published capex figures for a full AI datacenter, all estimates, and note carefully whether accelerators are included:

| Scope | $ per MW |
|---|---|
| Standard shell and core | $10.7–11.3M |
| AI-optimised shell with liquid cooling | $12–15M |
| AI facility plus tenant IT fit-out, **excluding GPUs** | $15–25M |
| **Full stack including GPUs (GB200 NVL72)** | **$30–45M** |
| Epoch AI model, US hyperscaler 1 GW GB200 build | **$38M upfront, $0.9M/yr opex, $8.5M/yr annualised TCO** |

Epoch's composition: servers ~56% of capex, facility MEP/shell/labour ~30%, network and cluster infrastructure ~13%. In *annualised* TCO, servers and GPUs are ~60% and energy only ~7% — which is why the depreciation-schedule debate matters more than the electricity bill, and why the asset's economic life is the accelerator's life, not the concrete's.

**The SemiAnalysis TPU-versus-GPU model** is the most rigorous public comparison, and every number in it is an estimate: Google's internal all-in TCO per Ironwood chip is roughly **44% below** a GB200 server; an external GCP customer sees roughly **30% below GB200 and 41% below GB300** per hour; and for Anthropic, assuming 40% MFU on TPU against 30% on GB300, cost per effective PFLOP is about **52% lower**, with a break-even MFU of 19%. The structural explanation is not that Broadcom's silicon is cheap — Google pays Broadcom a healthy margin — but that it is far less than the margin NVIDIA earns across the *whole system*: GPU, CPU, switch, NIC, memory, cabling and rack.

### 10.6 Export controls, as of August 2026

The policy environment is now a first-order determinant of who can buy what, and it has moved repeatedly.

| Date | Action |
|---|---|
| Oct 2022 | Initial BIS rule; A100/H100 restricted to China |
| Oct 2023 | Expanded; A800/H800 workaround parts also restricted |
| Dec 2024 | HBM and semiconductor equipment controls added |
| Jan 2025 | AI Diffusion Rule published — **rescinded 13 May 2025 before taking effect** |
| Apr 2025 | H20 licence requirement → NVIDIA takes a **$4.5B charge** |
| Aug 2025 | H20 and MI308 licences granted conditioned on a **15% revenue share** to the US government |
| Dec 2025 | H200 sales to China announced as permitted at **25%** |
| **13 Jan 2026** | BIS rule permitting case-by-case licences up to H200 / MI325X performance |
| **14 Jan 2026** | Presidential proclamation: **25% import tariff** on H200 and MI325X — the only two chips under both the rule and the tariff |
| May 2026 | ~10 Chinese firms cleared with a **75,000-unit cap each**; zero deliveries at that point |
| May 2026 | BIS extends licensing to China/Macau-headquartered entities **wherever they operate** |
| Aug 2026 | First H200 deliveries reach ByteDance and Tencent — roughly **10,000 units each, routed to Hong Kong**, outside the mainland customs border, on Beijing's instruction to protect domestic chipmakers |

(all confirmed from rule text, proclamations and company filings, except delivery volumes which are press-reported)

Two numbers frame the gap between policy and practice. The rule's 50% provision implies a ceiling somewhere around **817,000 to 900,000 H200-equivalents**; Chinese demand is estimated at about 2 million H200s. And NVIDIA's own guidance is unambiguous: as of 20 May 2026 it had "yet to generate any revenue" from H200 China licences and assumes **no China datacenter compute revenue** in guidance. The policy ceiling and the actual flow differ by roughly 50×.

For context on the alternative: Huawei's 2026 Ascend 910C production target is about 600,000 chips (up from ~200,000 in 2025) against Chinese demand of 1.0–1.5 million, constrained by SMIC 7nm yield and domestic HBM.

### 10.7 The money, confirmed

Because so much of this section is estimated, it is worth grounding in filings. NVIDIA's quarter ended 26 April 2026: **$81.6B total revenue (+85% YoY), $75.2B data center (+92%), of which $60.4B compute and $14.8B networking (+199%), at 74.9% GAAP gross margin.** Supply commitments rose to **$145B**. Management states "$1 trillion in Blackwell and Rubin revenue we foresee from 2025 through calendar 2027" and, on Rubin, "my sense is that we will be supply constrained throughout the entire life of Vera Rubin."

Broadcom, the TPU co-designer: Q2 FY26 AI semiconductor revenue **$10.8B (+143%)** against **>$30B of AI bookings**, guiding **$56B for FY2026** and **>$100B for FY2027**, with a Google supply assurance agreement running through 2031. Marvell's custom XPU revenue doubled to $1.5B in FY26. Amazon's chips business is at a **>$25B run rate**. (all confirmed)

That is the shape of the market: custom silicon is unambiguously real and growing faster in percentage terms, while NVIDIA still captures most of the dollars because it sells the CPU, the switch, the NIC and the rack alongside the accelerator.
