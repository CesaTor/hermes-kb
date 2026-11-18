# Attribuzione

`skills/llm-wiki` è un adattamento, per la KB ReQurv, della skill **`llm-wiki` v2.1.0** distribuita
con Hermes Agent (`optional-skills/research/llm-wiki`), a sua volta basata sul pattern
[LLM Wiki di Andrej Karpathy](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

La skill originale è distribuita con licenza MIT:

```text
MIT License

Copyright (c) Hermes Agent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Le modifiche ReQurv riguardano: la posizione della wiki nella KB, le fonti che non vengono copiate,
i nomi delle cartelle, la provenienza verso i documenti in forza, lo script `wiki_lint.py` e i
collegamenti alle skill `mappa-kb`, `knowledge-ingest` e `pubblica-documento`.
