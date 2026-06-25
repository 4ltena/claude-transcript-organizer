import argparse, sys
from transcript_organizer.config import load_config
from transcript_organizer.providers import get_provider
from transcript_organizer import pipeline, deleter

def build_parser():
    p = argparse.ArgumentParser(prog="organize",
                                description="Claude会話transcriptを整理しHANDOFFを更新する")
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("organize", help="抽出してHANDOFFを更新（削除しない）")
    o.add_argument("--config"); o.add_argument("--provider")
    o.add_argument("--project"); o.add_argument("--rebuild", action="store_true")
    o.add_argument("--dry-run", action="store_true")
    o.add_argument("--verbose", "-v", action="store_true",
                   help="会話ごとの読込・凝縮・分類・抽出をstderrに逐次出力")
    s = sub.add_parser("status", help="未処理件数・findings件数を表示")
    s.add_argument("--config")
    d = sub.add_parser("delete", help="処理済み会話をtrashへ退避（既定dry-run）")
    d.add_argument("--config"); d.add_argument("--project"); d.add_argument("--yes", action="store_true")
    return p

def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    cfg = load_config(args.config)
    if args.cmd == "organize":
        if args.provider:
            cfg.provider = args.provider
        prov = get_provider(cfg)
        logfn = (lambda m: print(m, file=sys.stderr)) if args.verbose else None
        r = pipeline.organize(cfg, prov, only_label=args.project,
                              rebuild=args.rebuild, dry_run=args.dry_run, log=logfn)
        print(f"処理: {r['processed']}件 / 新規finding: {r['added']}件 / "
              f"スキップ: {r['skipped']} / HANDOFF更新: {len(r['handoffs'])}件")
        if args.dry_run:
            print("（dry-run: 書き込みなし）")
        return 0
    if args.cmd == "status":
        r = pipeline.status(cfg)
        print(f"未処理: {r['unprocessed']}件 / 台帳: {r['ledger']}件 / "
              f"findings: {r['labels']}")
        return 0
    if args.cmd == "delete":
        plan = deleter.plan_deletion(cfg, only_label=args.project)
        if not args.yes:
            print(f"[dry-run] 削除候補: {len(plan['delete'])}件 / "
                  f"保護: {plan['protect']} （実行は --yes）")
            return 0
        res = deleter.execute(plan, cfg, yes=True)
        deleter.gc_trash(cfg)
        print(f"削除(trash退避): {res['deleted']}件 / 保護: {plan['protect']}")
        return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
