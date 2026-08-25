"""Revenue rollup. Sums the units count instead of the monetary amount,
producing plausible-but-wrong totals."""


def revenue_by_region(sales):
    out = {}
    for s in sales:
        region = s["region"]
        out[region] = out.get(region, 0) + s["units"]
    return out
