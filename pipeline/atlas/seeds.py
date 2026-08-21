"""Seed entities: the curated vocabulary the recogniser matches against.

Companies and supply-chain components are seeded rather than discovered, because
an alias list is a judgement call: "meta" is a company in one sentence and a
meta-description in another. Accelerators, data centers, cloud regions and
countries are discovered from records instead — they arrive with their own names.

Each company entry is (display name, aliases, domains). Domains drive the
`domain` recognition channel; aliases drive `field`, `path` and `text`.
"""

from __future__ import annotations

COMPANIES = {
    "nvidia": ("NVIDIA", ["nvidia", "nvda"], ["nvidia.com", "developer.nvidia.com",
                                              "blogs.nvidia.com", "nvidianews.nvidia.com",
                                              "investor.nvidia.com", "resources.nvidia.com",
                                              "images.nvidia.com", "docs.nvidia.com"]),
    "amd": ("AMD", ["amd", "instinct"], ["amd.com", "rocm.blogs.amd.com", "docs.amd.com"]),
    "intel": ("Intel", ["intel", "gaudi", "habana"], ["intel.com", "newsroom.intel.com",
                                                      "docs.habana.ai"]),
    "google": ("Google", ["google", "google cloud", "gcp", "alphabet", "deepmind"],
               ["google.com", "cloud.google.com", "blog.google", "docs.cloud.google.com",
                "datacenters.google", "sustainability.google", "googlecloudpresscorner.com",
                "discuss.google.dev", "storage.googleapis.com"]),
    "microsoft": ("Microsoft", ["microsoft", "azure", "msft"],
                  ["microsoft.com", "blogs.microsoft.com", "azure.microsoft.com",
                   "prices.azure.com", "techcommunity.microsoft.com", "news.microsoft.com"]),
    "amazon": ("Amazon / AWS", ["amazon", "aws", "amazon web services"],
               ["aws.amazon.com", "aboutamazon.com", "awsdocs-neuron.readthedocs-hosted.com",
                "repost.aws", "press.aboutamazon.com", "instances.vantage.sh"]),
    "meta": ("Meta", ["meta", "facebook", "mtia"],
             ["ai.meta.com", "datacenters.atmeta.com", "about.fb.com", "engineering.fb.com",
              "facebook.com"]),
    "openai": ("OpenAI", ["openai", "stargate"], ["openai.com"]),
    "anthropic": ("Anthropic", ["anthropic", "claude"], ["anthropic.com"]),
    "xai": ("xAI", ["xai", "x.ai", "colossus", "spacexai", "macrohard"], ["x.ai"]),
    "oracle": ("Oracle", ["oracle", "oci"], ["oracle.com", "blogs.oracle.com",
                                             "docs.oracle.com"]),
    "coreweave": ("CoreWeave", ["coreweave"], ["coreweave.com", "docs.coreweave.com",
                                               "wf.coreweave.com"]),
    "crusoe": ("Crusoe", ["crusoe"], ["crusoe.ai", "crusoeenergy.com"]),
    "tsmc": ("TSMC", ["tsmc", "cowos"], ["tsmc.com"]),
    "broadcom": ("Broadcom", ["broadcom", "avgo"], ["broadcom.com", "investors.broadcom.com"]),
    "sk_hynix": ("SK hynix", ["sk hynix", "hynix"], ["skhynix.com"]),
    "samsung": ("Samsung", ["samsung"], ["samsung.com", "news.samsung.com"]),
    "micron": ("Micron", ["micron"], ["micron.com"]),
    "huawei": ("Huawei", ["huawei", "ascend", "cloudmatrix"], ["huawei.com"]),
    "cerebras": ("Cerebras", ["cerebras", "wse"], ["cerebras.ai", "cerebras.net"]),
    "groq": ("Groq", ["groq"], ["groq.com", "groq.humain.ai"]),
    "sambanova": ("SambaNova", ["sambanova"], ["sambanova.ai"]),
    "tenstorrent": ("Tenstorrent", ["tenstorrent"], ["tenstorrent.com", "docs.tenstorrent.com"]),
    "nscale": ("Nscale", ["nscale"], ["nscale.com"]),
    "nebius": ("Nebius", ["nebius"], ["nebius.com", "docs.nebius.com"]),
    "lambda": ("Lambda", ["lambda labs", "lambda ai"], ["lambda.ai", "lambdalabs.com"]),
    "firmus": ("Firmus", ["firmus", "sustainable metal cloud"], ["firmus.co"]),
    "terawulf": ("TeraWulf", ["terawulf", "lake mariner"], ["terawulf.com",
                                                            "investors.terawulf.com"]),
    "cipher": ("Cipher Mining", ["cipher mining", "barber lake"], ["ciphermining.com"]),
    "fluidstack": ("Fluidstack", ["fluidstack"], ["fluidstack.io"]),
    "vantage": ("Vantage Data Centers", ["vantage"], ["vantage-dc.com"]),
    "qts": ("QTS", ["qts"], ["qtsdatacenters.com", "q.com"]),
    "equinix": ("Equinix", ["equinix"], ["equinix.com"]),
    "digital_realty": ("Digital Realty", ["digital realty"], ["digitalrealty.com"]),
    "stack": ("STACK Infrastructure", ["stack infrastructure"], ["stackinfra.com"]),
    "dayone": ("DayOne / GDS", ["dayone", "gds holdings"], ["dayonedc.com"]),
    "ytl": ("YTL", ["ytl"], ["ytl.com"]),
    "g42": ("G42", ["g42", "khazna", "core42"], ["g42.ai", "khaznadatacenters.com"]),
    "humain": ("Humain", ["humain"], ["humain.ai"]),
    "softbank": ("SoftBank", ["softbank", "sb energy"], ["softbank.jp", "sbenergy.com"]),
    "kddi": ("KDDI", ["kddi"], ["kddi.com", "newsroom.kddi.com"]),
    "naver": ("NAVER", ["naver"], ["navercorp.com"]),
    "foxconn": ("Foxconn", ["foxconn", "hon hai"], ["foxconn.com"]),
    "scala": ("Scala Data Centers", ["scala data"], ["scaladatacenters.com"]),
    "cassava": ("Cassava", ["cassava"], ["cassavatechnologies.com"]),
    "bell": ("Bell Canada", ["bell ai fabric", "bell canada"], ["bce.ca", "bell.ca"]),
    "telus": ("Telus", ["telus"], ["telus.com"]),
    "yotta": ("Yotta", ["yotta"], ["yotta.com"]),
    "reliance": ("Reliance", ["reliance industries", "reliance jio"], ["ril.com"]),
    "eurohpc": ("EuroHPC", ["eurohpc", "jupiter", "lumi", "leonardo", "marenostrum"],
                ["eurohpc-ju.europa.eu", "fz-juelich.de"]),
    "mistral": ("Mistral AI", ["mistral"], ["mistral.ai"]),
    "eclairion": ("Eclairion", ["eclairion"], ["eclairion.com"]),
    "vnet": ("VNET", ["vnet", "21vianet"], ["vnet.com"]),
    "alibaba": ("Alibaba", ["alibaba"], ["alibabacloud.com"]),
    "bytedance": ("ByteDance", ["bytedance", "tiktok"], ["bytedance.com"]),
    "tencent": ("Tencent", ["tencent"], ["tencent.com", "cloud.tencent.com"]),
    "epoch": ("Epoch AI", ["epoch ai"], ["epoch.ai"]),
    "mlcommons": ("MLCommons", ["mlcommons", "mlperf"], ["mlcommons.org"]),
    "semianalysis": ("SemiAnalysis", ["semianalysis"], ["semianalysis.com",
                                                        "newsletter.semianalysis.com"]),
    "trendforce": ("TrendForce", ["trendforce"], ["trendforce.com"]),
    "peeringdb": ("PeeringDB", ["peeringdb"], ["peeringdb.com"]),
}

COMPONENTS = {
    "hbm3e": ("HBM3E", ["hbm3e", "hbm3"]),
    "hbm4": ("HBM4", ["hbm4"]),
    "cowos": ("CoWoS packaging", ["cowos", "advanced packaging", "interposer"]),
    "nvlink": ("NVLink / NVSwitch", ["nvlink", "nvswitch", "nvl72"]),
    "infiniband": ("InfiniBand", ["infiniband", "quantum-x", "quantum x800"]),
    "ethernet_ai": ("AI Ethernet", ["spectrum-x", "ultra ethernet", "ualink", "roce"]),
    "liquid_cooling": ("Liquid cooling", ["liquid cool", "direct-to-chip", "immersion cool"]),
    "gas_turbine": ("On-site generation", ["gas turbine", "microgrid", "fuel cell",
                                           "on-site gas"]),
    "grid": ("Grid interconnect", ["interconnect queue", "substation", "transformer",
                                   "ercot", "oncor", "tva", "saskpower"]),
    "optical": ("Optical switching", ["optical circuit switch", "ocs", "co-packaged optics"]),
}


# Vendor strings as they appear in data/accelerators.csv, mapped to company ids.
VENDOR_TO_COMPANY = {
    "NVIDIA": "company:nvidia", "AMD": "company:amd", "Intel": "company:intel",
    "Google": "company:google", "AWS": "company:amazon", "Meta": "company:meta",
    "Microsoft": "company:microsoft", "Huawei": "company:huawei",
    "Cerebras": "company:cerebras", "Groq": "company:groq",
    "SambaNova": "company:sambanova", "Tenstorrent": "company:tenstorrent",
}

# Category shown on a company entity when nothing in the records says otherwise.
COMPANY_CATEGORY = {
    "company:nvidia": "vendor", "company:amd": "vendor", "company:intel": "vendor",
    "company:broadcom": "vendor", "company:cerebras": "vendor", "company:groq": "vendor",
    "company:sambanova": "vendor", "company:tenstorrent": "vendor",
    "company:huawei": "vendor", "company:tsmc": "foundry",
    "company:sk_hynix": "supplier", "company:samsung": "supplier",
    "company:micron": "supplier", "company:foxconn": "supplier",
    "company:google": "hyperscaler", "company:microsoft": "hyperscaler",
    "company:amazon": "hyperscaler", "company:meta": "hyperscaler",
    "company:oracle": "hyperscaler", "company:alibaba": "hyperscaler",
    "company:tencent": "hyperscaler", "company:bytedance": "hyperscaler",
    "company:openai": "lab", "company:anthropic": "lab", "company:xai": "lab",
    "company:mistral": "lab",
    "company:coreweave": "neocloud", "company:crusoe": "neocloud",
    "company:nebius": "neocloud", "company:nscale": "neocloud",
    "company:lambda": "neocloud", "company:fluidstack": "neocloud",
    "company:firmus": "neocloud", "company:terawulf": "neocloud",
    "company:cipher": "neocloud",
    "company:equinix": "colocation", "company:digital_realty": "colocation",
    "company:vantage": "colocation", "company:qts": "colocation",
    "company:stack": "colocation", "company:dayone": "colocation",
    "company:scala": "colocation", "company:ytl": "colocation",
    "company:epoch": "research", "company:mlcommons": "research",
    "company:semianalysis": "research", "company:trendforce": "research",
    "company:peeringdb": "registry",
    "company:g42": "operator", "company:humain": "operator",
    "company:softbank": "operator", "company:kddi": "operator",
    "company:naver": "operator", "company:cassava": "operator",
    "company:bell": "operator", "company:telus": "operator",
    "company:yotta": "operator", "company:reliance": "operator",
    "company:eurohpc": "research", "company:eclairion": "operator",
    "company:vnet": "operator",
}


def company_seeds():
    """(entity id, display name, aliases, domains) for every seeded company."""
    for key, (name, aliases, domains) in COMPANIES.items():
        yield f"company:{key}", name, aliases, domains


def component_seeds():
    for key, (name, aliases) in COMPONENTS.items():
        yield f"component:{key}", name, aliases


# Accelerator names as other tables write them, mapped onto the specification
# table's SKU. Each entry is a judgement that two names are the same silicon, so
# each carries its reason; anything genuinely different is left unmapped rather
# than merged.
ACCELERATOR_ALIASES = {
    "b200": ("accelerator:b200-hgx", "bare 'B200' in inventories means the HGX board"),
    "b200 sxm": ("accelerator:b200-hgx", "SXM module of the same board"),
    "gb200": ("accelerator:b200-nvl72", "Grace-Blackwell superchip, counted as NVL72 silicon"),
    "gb200 nvl72": ("accelerator:b200-nvl72", "rack form of the same part"),
    "gb200 superchip": ("accelerator:b200-nvl72", "rack form of the same part"),
    "b300": ("accelerator:b300-nvl72", "bare 'B300' means the NVL72 rack part"),
    "gb300": ("accelerator:b300-nvl72", "Grace-Blackwell Ultra superchip"),
    "gb300 nvl72": ("accelerator:b300-nvl72", "rack form of the same part"),
    "mi350x": ("accelerator:mi355x", "same die as MI355X, air-cooled lower-clock SKU"),
    "rubin": ("accelerator:rubin-r100", "family name for the R100 part"),
    "vr200": ("accelerator:rubin-r100", "Vera Rubin board carrying R100"),
    "a100": ("accelerator:a100-80gb", "bare 'A100' in site inventories is the 80GB SXM"),
    "h100 sxm": ("accelerator:h100", "SXM module is the H100 spec-table row"),
    "h800": ("accelerator:h100", "export SKU of the same die"),
    "tpu v6": ("accelerator:tpu-v6e", "only the v6e variant shipped externally"),
    "trn2": ("accelerator:trainium2", "AWS instance shorthand"),
    "trainium 2": ("accelerator:trainium2", "spacing variant"),
    "trn1": ("accelerator:trainium1", "AWS instance shorthand"),
    "trainium": ("accelerator:trainium2", "current generation when unqualified"),
    "ascend 910": ("accelerator:ascend-910b", "the 910B is the shipping 910"),
}
