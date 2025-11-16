#!/bin/bash

URLs=(
    "https://eminwon.jung.daegu.kr"
    "https://eminwon.suseong.kr"
    "https://eminwon.buk.daegu.kr"
    "https://eminwon.dong.daegu.kr"
    "https://eminwon.dgs.go.kr"
    "https://eminwon.nam.daegu.kr"
    "https://eminwon.dalseong.daegu.kr"
)

for url in "${URLs[@]}"; do
    echo "Crawling URL: $url"
    python crawling.py --url "$url"
done