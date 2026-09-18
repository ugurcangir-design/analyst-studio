# <Uygulama> — Akış Analizi (Index)

> Bu sayfa `<uygulama>` uygulamasının tüm kullanıcı akışlarının **ana dizinidir**. Her akış bir ALT sayfadır.
> Ortam: `<dev/uat>` · Başlangıç: `<tarih>` · Hedef: tüm akışlar `<tarih>`'e kadar.

## Amaç
<Neden bu analiz yapılıyor — 1-2 cümle.>

## Akış Envanteri
| # | Modül | Akış | Sahip | Durum | Sayfa |
|---|-------|------|-------|-------|-------|
| 1 | Kimlik | Giriş + OTP | `<analist>` | ✅ Onaylı | `<link>` |
| 2 | Kimlik | Kayıt | `<analist>` | 🟡 Taslak | `<link>` |
| 3 | <modül> | <akış> | `<analist>` | ⬜ Başlanmadı | — |
| … |  |  |  |  |  |

**Durum:** ⬜ Başlanmadı · 🟡 Taslak · ✅ Onaylı

## Bölüşüm (2 analist)
- **<Analist 1>:** `<modüller>`
- **<Analist 2>:** `<modüller>`

## Uçtan Uca Harita (opsiyonel — kapanışta)
```mermaid
flowchart LR
  A[Giriş] --> B[Ana Sayfa] --> C[<akış>] --> D[<akış>]
```

## Notlar / Kanonik Terimler
- <Uygulamaya özgü kanonik ad ↔ takma ad, tekrar eden kurallar.>
