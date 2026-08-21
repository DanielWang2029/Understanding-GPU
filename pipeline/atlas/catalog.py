"""The source catalog: one entry per data source, hand-maintained.

This is the only place a new data source has to be declared. Add an entry here,
write the matching adapter in `adapters.py`, and the rest of the pipeline —
records, recognition, entity filling, the UI's Data sources tab — picks it up
without further changes.

`trust` decides who wins when two sources claim the same entity parameter:

  0.95  the party itself, in a document of record (vendor datasheet, SEC filing,
        official price list, government rule)
  0.80  a provider's own API or docs describing its own service
  0.70  a research dataset with a published method
  0.60  our own derived tables, which are transparent but second-hand
  0.45  a modelled estimate over inference (satellite, permits, power)
  0.30  an aggregator or directory with no stated method
"""

from __future__ import annotations

CATALOG: list[dict] = [
    # ---------------------------------------------------------------- pipelines
    {
        "id": "datacenterview",
        "name": "dataCenterView pipeline export",
        "publisher": "dataCenterView project (uploaded)",
        "kind": "pipeline",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/references/datecenterview-main.zip",
        "access": "zip",
        "format": "json",
        "local_path": "references/datecenterview-main.zip",
        "adapter": "ingest_datacenterview",
        "licence": "As provided in the uploaded project",
        "attribution": "dataCenterView, data.json v1.2 (2026-08-07)",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "United States data centers with field-level provenance from an "
                 "agentic discover → extract → cross-vendor verify pipeline.",
        "record_kinds": ["site_profile", "site_capacity", "citation"],
        "entity_types": ["datacenter", "company", "country"],
        "fills": ["datacenter.operator", "datacenter.tenant", "datacenter.status",
                  "datacenter.city", "datacenter.region", "datacenter.country",
                  "datacenter.lat", "datacenter.lon", "datacenter.coord_precision",
                  "datacenter.power_mw", "datacenter.power_mw_planned",
                  "datacenter.first_operational", "datacenter.category",
                  "datacenter.capex_usd_b"],
        "trust": 0.55,
        "confidence_default": "estimate",
        "caveats": "US-only, and 398 of 490 records are flagged needs_review upstream. "
                   "capacity_mw is nameplate capacity, not energised load. Carries no "
                   "accelerator counts: its compute layer is an illustrative seed.",
    },
    # ---------------------------------------------------------------- datasets
    {
        "id": "epoch_datacenters",
        "name": "Epoch AI — AI Data Centers",
        "publisher": "Epoch AI",
        "kind": "dataset",
        "url": "https://epoch.ai/data/ai-data-centers",
        "access": "download",
        "format": "csv",
        "local_path": "data/sources/epoch_ai/data_centers.csv",
        "adapter": "ingest_epoch_sites",
        "licence": "CC-BY 4.0",
        "attribution": "Epoch AI, 'AI Data Centers'. Published online at epoch.ai.",
        "retrieved": "2026-08-20",
        "cadence": "monthly",
        "scope": "83 frontier AI data centers worldwide with modelled power, "
                 "H100-equivalents, capital cost, owners and users.",
        "record_kinds": ["site_profile", "site_capacity", "site_compute", "citation"],
        "entity_types": ["datacenter", "company", "country"],
        "fills": ["datacenter.operator", "datacenter.tenant", "datacenter.country",
                  "datacenter.power_mw", "datacenter.h100e", "datacenter.capex_usd_b",
                  "datacenter.accelerators_installed", "datacenter.category"],
        "trust": 0.45,
        "confidence_default": "estimate",
        "caveats": "Power, chip counts and capex are model outputs inferred from "
                   "satellite imagery, permits and utility filings — not company "
                   "disclosures. Coverage prioritises the US; no coordinates are "
                   "published, so addresses must be geocoded.",
    },
    {
        "id": "epoch_timelines",
        "name": "Epoch AI — data center build timelines",
        "publisher": "Epoch AI",
        "kind": "dataset",
        "url": "https://epoch.ai/data/ai-data-centers",
        "access": "download",
        "format": "csv",
        "local_path": "data/sources/epoch_ai/data_center_timelines.csv",
        "adapter": "ingest_epoch_timelines",
        "licence": "CC-BY 4.0",
        "attribution": "Epoch AI, 'AI Data Centers' (timelines table).",
        "retrieved": "2026-08-20",
        "cadence": "monthly",
        "scope": "492 dated observations of construction status, IT power and "
                 "H100-equivalents per site, including future-dated build plans.",
        "record_kinds": ["site_capacity", "site_compute"],
        "entity_types": ["datacenter"],
        "fills": ["datacenter.power_mw", "datacenter.power_mw_planned",
                  "datacenter.h100e", "datacenter.h100e_planned", "datacenter.status"],
        "trust": 0.45,
        "confidence_default": "estimate",
        "caveats": "The 'Construction status' column is a free-text observation note, "
                   "not an enum — status must be derived from the numbers. Rows dated "
                   "after the build date are projections.",
    },
    {
        "id": "epoch_chips",
        "name": "Epoch AI — per-site chip quantities",
        "publisher": "Epoch AI",
        "kind": "dataset",
        "url": "https://epoch.ai/data/ai-data-centers",
        "access": "download",
        "format": "csv",
        "local_path": "data/sources/epoch_ai/data_center_chip_quantities.csv",
        "adapter": "ingest_epoch_chips",
        "licence": "CC-BY 4.0",
        "attribution": "Epoch AI, 'AI Data Centers' (chip quantities table).",
        "retrieved": "2026-08-20",
        "cadence": "monthly",
        "scope": "225 rows of chip type and unit count per site per date — the only "
                 "public per-site accelerator census that exists.",
        "record_kinds": ["chip_inventory", "citation"],
        "entity_types": ["datacenter", "accelerator", "company"],
        "fills": ["datacenter.accelerators_installed", "datacenter.accelerators_planned",
                  "accelerator.deployed_units", "accelerator.sites_deployed"],
        "trust": 0.45,
        "confidence_default": "estimate",
        "caveats": "Counts are modelled from power and cooling capacity. Thirteen site "
                   "names appear here but not in the main table; one duplicates another "
                   "site under a different owner and is dropped by alias rule.",
    },
    # ------------------------------------------------------------- document sets
    {
        "id": "curated_global",
        "name": "Curated global sites",
        "publisher": "This repository",
        "kind": "document-set",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/compute_map/curated_sites.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/compute_map/curated_sites.csv",
        "adapter": "ingest_curated_sites",
        "licence": "Repository licence; underlying claims belong to their publishers",
        "attribution": "Assembled from company announcements, government publications "
                       "and trade press; every row carries its own source URLs.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "95 sites in 31 countries that Epoch does not cover — EuroHPC, "
                 "Nscale, Nebius, Humain, Stargate UAE, SoftBank, NAVER, Yotta, "
                 "Huawei, Firmus, Bell, Scala, Cassava and others.",
        "record_kinds": ["site_profile", "site_capacity", "site_compute", "citation"],
        "entity_types": ["datacenter", "company", "country", "accelerator"],
        "fills": ["datacenter.operator", "datacenter.tenant", "datacenter.status",
                  "datacenter.city", "datacenter.region", "datacenter.country",
                  "datacenter.lat", "datacenter.lon", "datacenter.coord_precision",
                  "datacenter.power_mw", "datacenter.power_mw_planned",
                  "datacenter.capex_usd_b", "datacenter.first_operational",
                  "datacenter.category"],
        "trust": 0.70,
        "confidence_default": "confirmed",
        "caveats": "Hand-assembled, so coverage reflects what was searched for. Each "
                   "row states its own confidence: 61 confirmed, 27 estimate, 7 rumor.",
    },
    {
        "id": "provider_docs",
        "name": "Cloud provider documentation and pricing APIs",
        "publisher": "Google Cloud, AWS, Microsoft Azure, Oracle, CoreWeave",
        "kind": "api",
        "url": "https://cloud.google.com/tpu/docs/regions-zones",
        "access": "manual",
        "format": "csv",
        "local_path": "data/compute_map/accelerator_regions.csv",
        "adapter": "ingest_regions",
        "licence": "Provider documentation, cited",
        "attribution": "Provider region/zone documentation and retail pricing APIs.",
        "retrieved": "2026-08-20",
        "cadence": "continuous",
        "scope": "53 cloud regions with the accelerator generations each can "
                 "provision, and the physical metro serving each region.",
        "record_kinds": ["region_availability", "citation"],
        "entity_types": ["cloud_region", "company", "accelerator", "country"],
        "fills": ["cloud_region.provider", "cloud_region.region_id",
                  "cloud_region.label", "cloud_region.city", "cloud_region.country",
                  "cloud_region.lat", "cloud_region.lon",
                  "cloud_region.accelerators", "cloud_region.detail",
                  "cloud_region.status"],
        "trust": 0.80,
        "confidence_default": "confirmed",
        "caveats": "A region is a metro, not a building. Providers publish where a SKU "
                   "can be provisioned, never how many chips are installed.",
    },
    # ------------------------------------------------------------ derived tables
    {
        "id": "accelerators",
        "name": "Accelerator specification table",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/accelerators.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/accelerators.csv",
        "adapter": "ingest_accelerators",
        "licence": "Repository licence",
        "attribution": "Compiled from vendor datasheets and architecture whitepapers; "
                       "see report/report.md for per-figure sourcing.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "49 accelerators from 12 vendors: process, memory, dense throughput "
                 "at each precision, TDP, fabric, scale-up domain and unit price.",
        "record_kinds": ["chip_spec"],
        "entity_types": ["accelerator", "company"],
        "fills": ["accelerator.vendor", "accelerator.family", "accelerator.role",
                  "accelerator.launch", "accelerator.process", "accelerator.memory_gb",
                  "accelerator.memory_type", "accelerator.memory_bw_tbs",
                  "accelerator.dense_bf16_tflops", "accelerator.dense_fp8_tflops",
                  "accelerator.dense_fp4_tflops", "accelerator.tdp_w",
                  "accelerator.scaleup_bw_gbs", "accelerator.scaleup_domain",
                  "accelerator.unit_price_usd"],
        "trust": 0.60,
        "confidence_default": "confirmed",
        "caveats": "All throughput figures are dense: vendor headline numbers that "
                   "assume 2:1 sparsity have been halved. Unpublished values are blank "
                   "rather than interpolated.",
    },
    {
        "id": "cloud_pricing",
        "name": "Cloud accelerator pricing",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/cloud_pricing.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/cloud_pricing.csv",
        "adapter": "ingest_pricing",
        "licence": "Repository licence",
        "attribution": "Vendor rate cards plus price trackers, per row.",
        "retrieved": "2026-08-20",
        "cadence": "monthly",
        "scope": "59 offers across 12 providers and 9 pricing tiers, per chip-hour.",
        "record_kinds": ["chip_price"],
        "entity_types": ["accelerator", "company"],
        "fills": ["accelerator.cheapest_rental_usd_hr"],
        "trust": 0.60,
        "confidence_default": "confirmed",
        "caveats": "Marketplace and spot rows are host-set and volatile; the same "
                   "silicon spans a 45x price range across tiers.",
    },
    {
        "id": "supply_chain",
        "name": "Supply-chain metrics",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/supply_chain.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/supply_chain.csv",
        "adapter": "ingest_supply",
        "licence": "Repository licence",
        "attribution": "TrendForce, supplier disclosures, analyst estimates, per row.",
        "retrieved": "2026-08-20",
        "cadence": "quarterly",
        "scope": "CoWoS capacity and demand, HBM share and pricing, wafer prices, "
                 "unit-shipment estimates and rack power, 2023-2027.",
        "record_kinds": ["supply_metric"],
        "entity_types": ["component", "company"],
        "fills": ["component.unit_price_usd", "component.suppliers"],
        "trust": 0.45,
        "confidence_default": "estimate",
        "caveats": "No supplier reports HBM revenue separately, so share figures are "
                   "estimates that disagree between sources by up to 20 points.",
    },
    {
        "id": "bom_costs",
        "name": "Modelled bills of materials",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/bom_costs.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/bom_costs.csv",
        "adapter": "ingest_bom",
        "licence": "Repository licence",
        "attribution": "Raymond James teardown lineage, extended by Epoch AI, "
                       "TrendForce and SemiAnalysis.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "Six accelerators broken into logic die, HBM, packaging and assembly "
                 "cost, with a modelled sell price.",
        "record_kinds": ["cost_model"],
        "entity_types": ["accelerator", "component"],
        "fills": ["component.consumed_by"],
        "trust": 0.45,
        "confidence_default": "estimate",
        "caveats": "No vendor discloses per-part cost of goods; every figure is a model.",
    },
    {
        "id": "mlperf",
        "name": "MLPerf Training results",
        "publisher": "MLCommons",
        "kind": "derived",
        "url": "https://mlcommons.org/benchmarks/training/",
        "access": "repo",
        "format": "csv",
        "local_path": "data/mlperf_training.csv",
        "adapter": "ingest_mlperf",
        "licence": "MLCommons results are public; table compiled here",
        "attribution": "MLCommons MLPerf Training v4.0 through v6.0 result sets.",
        "retrieved": "2026-08-20",
        "cadence": "quarterly",
        "scope": "29 audited time-to-train results by benchmark, platform and scale.",
        "record_kinds": ["benchmark_result"],
        "entity_types": ["accelerator", "company"],
        "fills": [],
        "trust": 0.95,
        "confidence_default": "confirmed",
        "caveats": "Submitters choose their own scale, and the closed division has no "
                   "perf-per-dollar or perf-per-watt metric.",
    },
    {
        "id": "rack_systems",
        "name": "Rack and pod systems",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/rack_systems.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/rack_systems.csv",
        "adapter": "ingest_racks",
        "licence": "Repository licence",
        "attribution": "Vendor reference architectures and datasheets.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "13 rack- and pod-scale systems: chips, compute, memory, fabric, "
                 "power and price.",
        "record_kinds": ["chip_spec", "supply_metric"],
        "entity_types": ["accelerator", "company", "component"],
        "fills": ["component.consumed_by"],
        "trust": 0.60,
        "confidence_default": "confirmed",
        "caveats": "A TPU superpod is ~128 racks' worth of chips, so per-system totals "
                   "are not comparable across rows.",
    },
    {
        "id": "training_runs",
        "name": "Published training runs",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/data/training_runs.csv",
        "access": "repo",
        "format": "csv",
        "local_path": "data/training_runs.csv",
        "adapter": "ingest_runs",
        "licence": "Repository licence",
        "attribution": "Model papers and cards, plus Epoch AI compute estimates.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "14 model training runs with parameters, tokens, FLOPs, hardware, "
                 "chip-hours and MFU where published.",
        "record_kinds": ["training_run"],
        "entity_types": ["company", "accelerator"],
        "fills": [],
        "trust": 0.70,
        "confidence_default": "confirmed",
        "caveats": "Frontier labs stopped publishing compute after 2024, so later rows "
                   "are reconstructions from hardware counts and durations.",
    },
    {
        "id": "compute_map",
        "name": "Compute map resolved sites",
        "publisher": "This repository",
        "kind": "derived",
        "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/docs/compute-map/data.json",
        "access": "repo",
        "format": "json",
        "local_path": "docs/compute-map/data.json",
        "adapter": "ingest_compute_map_identity",
        "licence": "Repository licence",
        "attribution": "scripts/build_compute_map.py output.",
        "retrieved": "2026-08-20",
        "cadence": "ad-hoc",
        "scope": "The identity layer: 631 canonical sites with their merge decisions, "
                 "best coordinates and alias names, used as the prior for entity "
                 "resolution rather than re-solving geographic dedup here.",
        "record_kinds": ["site_profile", "geo_profile"],
        "entity_types": ["datacenter", "cloud_region", "country"],
        "fills": ["datacenter.lat", "datacenter.lon", "datacenter.coord_precision",
                  "datacenter.country", "datacenter.city", "datacenter.region",
                  "country.iso3", "country.continent"],
        "trust": 0.60,
        "confidence_default": "estimate",
        "caveats": "Derived, so it inherits every caveat of its four inputs. Used here "
                   "for identity and geometry, not as an independent claim.",
    },
]

# Curated facts that no ingested source in this repository carries. Kept
# separate from the adapters so the provenance stays honest: these are marked
# fill="manual" in the schema and appear as source "curated_manual".
MANUAL_FACTS: dict[str, dict] = {
    "company:nvidia": {"founded": 1993, "ceo": "Jensen Huang", "ticker": "NVDA",
                       "headquarters": "Santa Clara, United States", "country": "United States"},
    "company:amd": {"founded": 1969, "ceo": "Lisa Su", "ticker": "AMD",
                    "headquarters": "Santa Clara, United States", "country": "United States"},
    "company:intel": {"founded": 1968, "ceo": "Lip-Bu Tan", "ticker": "INTC",
                      "headquarters": "Santa Clara, United States", "country": "United States"},
    "company:google": {"founded": 1998, "ceo": "Sundar Pichai", "ticker": "GOOGL",
                       "headquarters": "Mountain View, United States", "country": "United States"},
    "company:microsoft": {"founded": 1975, "ceo": "Satya Nadella", "ticker": "MSFT",
                          "headquarters": "Redmond, United States", "country": "United States"},
    "company:amazon": {"founded": 1994, "ceo": "Andy Jassy", "ticker": "AMZN",
                       "headquarters": "Seattle, United States", "country": "United States"},
    "company:meta": {"founded": 2004, "ceo": "Mark Zuckerberg", "ticker": "META",
                     "headquarters": "Menlo Park, United States", "country": "United States"},
    "company:openai": {"founded": 2015, "ceo": "Sam Altman",
                       "headquarters": "San Francisco, United States", "country": "United States"},
    "company:anthropic": {"founded": 2021, "ceo": "Dario Amodei",
                          "headquarters": "San Francisco, United States", "country": "United States"},
    "company:xai": {"founded": 2023, "ceo": "Elon Musk",
                    "headquarters": "Palo Alto, United States", "country": "United States"},
    "company:oracle": {"founded": 1977, "ceo": "Safra Catz", "ticker": "ORCL",
                       "headquarters": "Austin, United States", "country": "United States"},
    "company:coreweave": {"founded": 2017, "ceo": "Michael Intrator", "ticker": "CRWV",
                          "headquarters": "Livingston, United States", "country": "United States"},
    "company:crusoe": {"founded": 2018, "ceo": "Chase Lochmiller",
                       "headquarters": "Denver, United States", "country": "United States"},
    "company:tsmc": {"founded": 1987, "ceo": "C. C. Wei", "ticker": "TSM",
                     "headquarters": "Hsinchu, Taiwan", "country": "Taiwan"},
    "company:broadcom": {"founded": 1961, "ceo": "Hock Tan", "ticker": "AVGO",
                         "headquarters": "Palo Alto, United States", "country": "United States"},
    "company:sk_hynix": {"founded": 1983, "ceo": "Kwak Noh-jung", "ticker": "000660.KS",
                         "headquarters": "Icheon, South Korea", "country": "South Korea"},
    "company:samsung": {"founded": 1969, "ceo": "Jun Young-hyun", "ticker": "005930.KS",
                        "headquarters": "Suwon, South Korea", "country": "South Korea"},
    "company:micron": {"founded": 1978, "ceo": "Sanjay Mehrotra", "ticker": "MU",
                       "headquarters": "Boise, United States", "country": "United States"},
    "company:huawei": {"founded": 1987, "ceo": "Ren Zhengfei",
                       "headquarters": "Shenzhen, China", "country": "China"},
    "company:cerebras": {"founded": 2016, "ceo": "Andrew Feldman",
                         "headquarters": "Sunnyvale, United States", "country": "United States"},
    "company:groq": {"founded": 2016, "ceo": "Jonathan Ross",
                     "headquarters": "Mountain View, United States", "country": "United States"},
    "company:sambanova": {"founded": 2017, "ceo": "Rodrigo Liang",
                          "headquarters": "Palo Alto, United States", "country": "United States"},
    "company:tenstorrent": {"founded": 2016, "ceo": "Jim Keller",
                            "headquarters": "Toronto, Canada", "country": "Canada"},
    "company:nebius": {"founded": 2024, "ceo": "Arkady Volozh", "ticker": "NBIS",
                       "headquarters": "Amsterdam, Netherlands", "country": "Netherlands"},
    "company:nscale": {"founded": 2024, "ceo": "Josh Payne",
                       "headquarters": "London, United Kingdom", "country": "United Kingdom"},
    "company:terawulf": {"founded": 2021, "ceo": "Paul Prager", "ticker": "WULF",
                         "headquarters": "Easton, United States", "country": "United States"},
    "company:g42": {"founded": 2018, "ceo": "Peng Xiao",
                    "headquarters": "Abu Dhabi, United Arab Emirates",
                    "country": "United Arab Emirates"},
    "company:humain": {"founded": 2025, "ceo": "Tareq Amin",
                       "headquarters": "Riyadh, Saudi Arabia", "country": "Saudi Arabia"},
    "company:softbank": {"founded": 1981, "ceo": "Masayoshi Son", "ticker": "9984.T",
                         "headquarters": "Tokyo, Japan", "country": "Japan"},
    "company:equinix": {"founded": 1998, "ceo": "Adaire Fox-Martin", "ticker": "EQIX",
                        "headquarters": "Redwood City, United States", "country": "United States"},
    "company:digital_realty": {"founded": 2004, "ceo": "Andy Power", "ticker": "DLR",
                               "headquarters": "Austin, United States", "country": "United States"},
    "company:vantage": {"founded": 2010, "ceo": "Dana Adams",
                        "headquarters": "Denver, United States", "country": "United States"},
    "company:qts": {"founded": 2003, "ceo": "Tag Greason",
                    "headquarters": "Overland Park, United States", "country": "United States"},
    "company:epoch": {"founded": 2022, "ceo": "Jaime Sevilla",
                      "headquarters": "Remote", "country": "United Kingdom"},
    "company:mlcommons": {"founded": 2020, "headquarters": "San Francisco, United States",
                          "country": "United States"},

    # component descriptions: category, role and constraint are curated by design
    "component:hbm3e": {"category": "memory", "role": "High-bandwidth memory stacked on "
                        "the accelerator package; the generation shipping through 2026.",
                        "constraint": "All three suppliers sold out their 2026 capacity."},
    "component:hbm4": {"category": "memory", "role": "The 2026-27 memory generation, "
                       "doubling interface width; ships on Rubin and MI455X.",
                       "constraint": "Priced 55-70% above HBM3E per stack."},
    "component:cowos": {"category": "packaging", "role": "TSMC's 2.5D advanced packaging, "
                        "which places logic dies and HBM stacks on one interposer.",
                        "constraint": "Interposer area, not wafer starts, has gated "
                                      "accelerator supply since 2023."},
    "component:nvlink": {"category": "fabric", "role": "NVIDIA's coherent scale-up fabric "
                         "and the switches that build a 72-GPU domain.",
                         "constraint": "Proprietary; the domain size caps tensor parallelism."},
    "component:infiniband": {"category": "fabric", "role": "Scale-out network for GPU "
                             "clusters, 400G NDR and 800G XDR.",
                             "constraint": "Being displaced by Ethernet at frontier scale."},
    "component:ethernet_ai": {"category": "fabric", "role": "Spectrum-X, Ultra Ethernet and "
                              "UALink: open alternatives for scale-up and scale-out.",
                              "constraint": "Ecosystem maturity rather than physics."},
    "component:liquid_cooling": {"category": "cooling", "role": "Direct-to-chip and "
                                 "immersion cooling, mandatory above ~100 kW per rack.",
                                 "constraint": "Retrofitting air-cooled halls is often "
                                               "impossible."},
    "component:gas_turbine": {"category": "power", "role": "On-site generation and fuel "
                              "cells bridging the gap until a utility interconnect lands.",
                              "constraint": "Turbine delivery slots run multi-year."},
    "component:grid": {"category": "power", "role": "Utility interconnects, substations and "
                       "large power transformers.",
                       "constraint": "Transformer lead times exceed 50 weeks; "
                                     "interconnection queues are years long."},
    "component:optical": {"category": "optics", "role": "Optical circuit switching and "
                          "co-packaged optics; how a TPU pod reconfigures its torus.",
                          "constraint": "Google's OCS remains structurally unique."},
}

MANUAL_SOURCE = {
    "id": "curated_manual",
    "name": "Curated entity facts",
    "publisher": "This repository",
    "kind": "derived",
    "url": "https://github.com/DanielWang2029/Understanding-GPU/blob/main/pipeline/atlas/catalog.py",
    "access": "repo",
    "format": "markdown",
    "local_path": "pipeline/atlas/catalog.py",
    "adapter": "ingest_manual_facts",
    "licence": "Repository licence",
    "attribution": "Hand-entered company and component attributes.",
    "retrieved": "2026-08-21",
    "cadence": "ad-hoc",
    "scope": "Founding year, chief executive, headquarters and ticker for 35 companies, "
             "plus the category, role and constraint of 10 supply-chain components — "
             "attributes no ingested dataset in this repository carries.",
    "record_kinds": ["citation"],
    "entity_types": ["company", "component"],
    "fills": ["company.founded", "company.ceo", "company.headquarters",
              "company.country", "company.ticker", "component.category",
              "component.role", "component.constraint"],
    "trust": 0.65,
    "confidence_default": "confirmed",
    "caveats": "Hand-entered and undated: chief executives and tickers change. These are "
               "the only values in the registry with no document behind them.",
}


def catalog() -> list[dict]:
    return [*CATALOG, MANUAL_SOURCE]


def by_id() -> dict[str, dict]:
    return {s["id"]: s for s in catalog()}
