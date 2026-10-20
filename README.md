# free-media

Vlastní skill a malé Python CLI pro tvorbu obrázků a krátkých videí přes dvě veřejná Hugging Face ZeroGPU Spaces. Podporuje text-to-image, text-to-video i referenční obrázky pro úpravy a image-to-video. Při pokračování příběhu vede ke kontrole vzhledu stejných postav v každém záběru.

## Dva ověřené backendy

| Volba CLI | Oficiální Space | Výchozí nastavení |
| --- | --- | --- |
| `image` | [black-forest-labs/FLUX.2-klein-4B](https://huggingface.co/spaces/black-forest-labs/FLUX.2-klein-4B) | 1024 × 576, distilled, 4 kroky |
| `video` | [Lightricks/LTX-2.5](https://huggingface.co/spaces/Lightricks/LTX-2.5) | 896 × 512, 2 sekundy, dekodér `conv` |

Zdrojový kód, veřejná rozhraní a ZeroGPU cesta byly ověřeny 20. 10. 2026. Před každou novou generací CLI znovu kontroluje běžící ZeroGPU, schválenou revizi Space a pořadí parametrů veřejného endpointu. Dostupnost a kvóta služby se mohou měnit; úspěšné `inspect` nepotvrzuje dokončenou generaci. Podklady, licence kódu a vah i omezení jsou v [přehledu backendů](skills/free-media/references/backends.md).

## Pouze bezplatný anonymní režim

Klient nepoužívá HF token, uložené přihlašovací údaje ani relaci prohlížeče. Nepřepíná na placené API, HF Jobs nebo pronajatou GPU. Enhancer, automatická změna seedu i automatické prodlužování videa jsou vypnuté. Při vyčerpané kvótě, požadavku na přihlášení, změně schématu či revize nebo neověřitelném ZeroGPU se zastaví. Větší kvótu přihlášeného HF účtu tato verze nevyužívá.

Stačí **Python 3.10+ a přístup k internetu**. Skript používá standardní knihovnu Pythonu; nejsou potřeba další Python balíčky, místní GPU ani instalace modelů. Při generování odešle prompt a případné reference do zvoleného veřejného Space. Vstupy a výsledky ukládejte mimo tento repozitář.

## Rychlé použití

Příkazy spouštějte z kořene staženého projektu. Nejprve ověřte zvolený backend:

```bash
python3 skills/free-media/scripts/free_media.py inspect --backend image
python3 skills/free-media/scripts/free_media.py inspect --backend video
```

Připravte soubor s obecným promptem v UTF-8 vedle repozitáře:

```bash
mkdir -p ../free-media-work
cat > ../free-media-work/prompt.txt <<'EOF'
A peaceful illustrated garden in warm evening light. A gentle breeze moves a few leaves. Calm fixed camera, soft colors, no text.
EOF
```

Jeden obrázek:

```bash
python3 skills/free-media/scripts/free_media.py generate \
  --backend image \
  --prompt-file ../free-media-work/prompt.txt \
  --output-dir ../free-media-work/image-01 \
  --width 1024 --height 576 --seed 42
```

Pro následující dvousekundové video nejprve uložte zvolenou a prohlédnutou PNG předlohu jako `../free-media-work/reference.png`. Bez řádku `--reference` vzniká video pouze z textu.

```bash
python3 skills/free-media/scripts/free_media.py generate \
  --backend video \
  --prompt-file ../free-media-work/prompt.txt \
  --reference ../free-media-work/reference.png \
  --output-dir ../free-media-work/video-01 \
  --width 896 --height 512 --duration 2 --seed 42
```

Každému novému záběru dejte vlastní výstupní adresář. CLI do něj uloží `request.json` se stavem úlohy a po dokončení soubor `output` s příslušnou příponou. Manifest obsahuje i prompt a údaje o referencích, proto nepatří do Gitu. Dokončení potvrzuje až stav `complete` a existující výstup.

### Pokračování přerušeného čekání

Jedno `generate` založí nejvýše jednu úlohu a automaticky ji znovu neodesílá. Pokud se přeruší čekání nebo stahování a manifest má uložené `event_id`, použijte:

```bash
python3 skills/free-media/scripts/free_media.py resume \
  --manifest ../free-media-work/video-01/request.json
```

`resume` pouze převezme výsledek existující úlohy. Pokud identifikátor chybí, nelze bezpečně určit, zda server požadavek přijal; novou generaci automaticky nespouštějte. Ukončené úlohy tento příkaz znovu nestahuje. Případný zámek po havárii odstraňujte až po ověření, že původní proces už neběží.

## Kontrola výsledku a použití skillu

**Vizuální kontrola je povinnou součástí postupu.** Otevřete uložený obrázek; u videa prohlédněte začátek, prostředek a konec. Zkontrolujte počet a vzhled postav, anatomii, provedenou akci a návaznost. Stejný seed nezaručuje stejnou identitu. Delší příběh skládejte z krátkých, jednotlivě zkontrolovaných záběrů.

Úplný postup je v [SKILL.md](skills/free-media/SKILL.md), metadata v [agents/openai.yaml](skills/free-media/agents/openai.yaml) a lokální testy v [test_free_media.py](skills/free-media/scripts/test_free_media.py). Repo obsahuje připravený balíček; jeho uložení na GitHub skill automaticky neinstaluje. Instalaci do systémové složky v prostředí, kde vznikl, zastavila automatická kontrola oprávnění. CLI lze používat přímo z této kopie.
