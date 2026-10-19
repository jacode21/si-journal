#!/usr/bin/env bash
# Lighthouse summary: ./lh.sh <outdir> [url...]
out=$1; shift; mkdir -p "$out"
urls=${@:-"https://jacode21.github.io/si-journal/ https://jacode21.github.io/si-journal/issues/2026-10-19/"}
for u in $urls; do
  n=$(echo "$u" | sed 's|https://jacode21.github.io/si-journal/||; s|/$||; s|/|-|g'); n=${n:-home}
  for ff in mobile desktop; do
    pre=""; [ $ff = desktop ] && pre="--preset=desktop"
    CHROME_PATH=/usr/bin/google-chrome npx -y lighthouse@12.8.2 "$u" $pre --quiet --chrome-flags="--headless=new --no-sandbox" \
      --only-categories=performance,accessibility,best-practices,seo --output=json --output-path="$out/lh-$n-$ff.json" >/dev/null 2>&1
    python3 -c "
import json,sys; r=json.load(open('$out/lh-$n-$ff.json')); c=r['categories']; a=r['audits']
print('$n $ff', ' '.join(f\"{k}={round(v['score']*100)}\" for k,v in c.items()), 'LCP', a['largest-contentful-paint']['displayValue'], 'CLS', a['cumulative-layout-shift']['displayValue'], 'TBT', a['total-blocking-time']['displayValue'])
fails=[k for k,v in a.items() if v.get('score') is not None and v['score']<0.9 and v.get('scoreDisplayMode') in ('binary','numeric','metricSavings')]
print('   below 0.9:', ', '.join(fails[:14]))"
  done
done
