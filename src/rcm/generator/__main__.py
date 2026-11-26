"""Command line: python -m rcm.generator --seed 42 --claims 100000 --months 18"""

import argparse
from datetime import date

from rcm.generator.build import generate
from rcm.generator.config import GeneratorConfig
from rcm.generator.io import RAW_DIR_ENV, resolve_out_dir, write_tables


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rcm.generator", description="Write synthetic claims and remits to Parquet."
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--claims", type=int, default=100_000)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2025, 1, 1))
    parser.add_argument("--providers", type=int, default=200)
    parser.add_argument(
        "--out", default=None, help=f"output folder (default: ${RAW_DIR_ENV} or data/raw)"
    )
    args = parser.parse_args(argv)

    try:
        config = GeneratorConfig(
            seed=args.seed,
            n_claims=args.claims,
            months=args.months,
            start_date=args.start_date,
            n_providers=args.providers,
        )
    except ValueError as err:
        parser.error(str(err))

    tables = generate(config)
    out_dir = resolve_out_dir(args.out)
    write_tables(tables, out_dir)

    denial_rate = (tables["remits"]["claim_status"] != "paid").mean()
    print(f"Wrote {len(tables)} tables to {out_dir}")
    for name, df in tables.items():
        print(f"  {name:<18} {len(df):>9,} rows")
    print(f"Denial rate: {denial_rate:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
