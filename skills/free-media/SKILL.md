---
name: free-media
description: Vytvářet obrázky a krátká videa pouze bezplatnou cestou. Použít pro text-to-photo, text-to-image, úpravy referenčního obrázku, text-to-video, image-to-video a pokračování příběhů se stejnými postavami, když uživatel požaduje zdarma, otevřené modely nebo vlastní opakovatelný postup.
---

# Obrázky a videa zdarma

## Bezplatný režim

Používat přiložené CLI v anonymním režimu bez HF tokenu. Nepřebírat přihlašovací údaje z prostředí, uloženého účtu ani prohlížeče. Nepřepínat na placené API, HF Jobs, pronajatou GPU, předplatné nebo kredity. Požadavek „zdarma“ nesplňovat pouhou dostupností zdrojového kódu; ověřit i způsob spuštění.

Při požadavku na přihlášení, vyčerpané kvótě, platbě, změně schématu nebo neověřitelném ZeroGPU runtime zastavit generování a přesně popsat překážku. Nežádat automaticky o souhlas s placením. Už autorizovaný bezplatný krok provést bez opakovaného potvrzování.

## Provedení

1. **Připravit vstup.** Prohlédnout referenční obrázek. Zapsat prompt do souboru v pracovním adresáři úkolu mimo skill a Git. Pro navazující příběh určit neměnné rysy postav, počet, proporce a poslední známý dějový stav. Přečíst [backends.md](references/backends.md) při prvním použití nebo změně backendu.
2. **Ověřit a spustit jeden požadavek.** Spustit `inspect` pro zvolený backend. Před generováním programově ověřit ZeroGPU, revizi a očekávané endpointové schéma. Volit nejprve jeden obrázek nebo dvousekundový klip. Vypnout enhancer, náhodnou změnu seedu a automatické prodlužování videa. Pro jeden zamýšlený výstup použít `generate` nejvýše jednou; polling již přijatého požadavku není nová generace. Po timeoutu bez jasného výsledku nic automaticky neodesílat znovu.
3. **Zkontrolovat a předat výsledek.** Otevřít skutečný uložený výstup, u videa zkontrolovat začátek, prostředek i konec. Ověřit počet a vzhled postav, anatomii a splnění akce. Oddělit „backend dostupný“, „požadavek přijatý“ a „výstup dokončený“. Uvést jen skutečně provedenou kontrolu, místo neověřeného příslibu uvést zbývající omezení.

## CLI

Spouštět z adresáře skillu. Pokud `scripts/free_media.py` chybí, označit balíček jako neúplný návrh; nevydávat jej za funkční instalaci.

```bash
python3 scripts/free_media.py inspect --backend image
python3 scripts/free_media.py inspect --backend video
```

Obecný příklad: připravit `/tmp/free-media/prompt.txt` s popisem zahrady a jemného pohybu listí; případný obrázek ponechat mimo adresář skillu.

```bash
python3 scripts/free_media.py generate --backend image --prompt-file /tmp/free-media/prompt.txt --output-dir /tmp/free-media/image-01 --width 1024 --height 576 --seed 42
python3 scripts/free_media.py generate --backend video --prompt-file /tmp/free-media/prompt.txt --reference /tmp/free-media/reference.png --output-dir /tmp/free-media/video-01 --width 896 --height 512 --duration 2 --seed 42
```

`--reference` je volitelný lokální obrázek; bez něj jde o generování z textu. `--duration` použít pro video. Zadat rozměry a délku v mezích aktuálně ověřeného schématu. Metadata, prompty, vstupy a výstupy ukládat pouze k úkolu, nikoli do skillu nebo jeho repozitáře.

Každému novému záběru dát vlastní výstupní adresář. Po přerušení sběru výsledku použít `python3 scripts/free_media.py resume --manifest /tmp/free-media/video-01/request.json`; tím se nestartuje nová generace. Pokud proces havaroval se zámkem, nejprve ověřit, že už neběží; zámek neodstraňovat za běhu jiného procesu. Skript vyžaduje Python 3.10 nebo novější, nestahuje modely a nepotřebuje lokální GPU. Anonymní režim nevyužívá větší kvótu propojeného HF účtu.

## Zachování postav

Použít původní předlohu při přípravě každého nového záběru. Zamknout siluetu, barvy, velikost, počet končetin a rozlišovací znaky; promptem řídit hlavně novou akci a kameru. Začít jednou jednoduchou akcí s klidnou kamerou. Stejný seed používat pro porovnání, nepovažovat jej za záruku stejné identity.

Delší příběh rozdělit na krátké záběry. Po každém záběru ověřit kontinuitu před pokračováním; nepředávat deformovanou postavu jako další referenci. Nepoužívat soukromé příběhy, jména ani obrázky jako příklady v distribuovaném skillu.

## Rozsah

CLI obsluhuje dvě veřejná ZeroGPU Spaces uvedená v referenci. Lokální GPU alternativy chápat jako podklady pro budoucí implementaci; neoznačovat je za nainstalované nebo dostupné přes toto CLI. Instalace modelů, tvorba vlastního Space a publikování nejsou součástí samotného volání generace.

Výsledek stručně popsat česky, uvést skutečný stav a jeden další konkrétní krok. Hotové soubory zpřístupnit podle pravidel prostředí; interní soubory skillu uživateli nevracet jako náhradu za instalovaný skill.
