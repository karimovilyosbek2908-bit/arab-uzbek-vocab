# Google Cloud "Always Free" da botni ishga tushirish

Bot polling rejimida — faqat **chiquvchi** internet kerak. Port, domen, HTTPS
kerak emas.

## 0. Nima bepul (Always Free, sinov emas — doimiy)

- **1 ta `e2-micro` VM** har oy, quyidagi regionlardan birida:
  `us-west1` (Oregon), `us-central1` (Iowa), `us-east1` (South Carolina)
- 30 GB standart disk (SSD emas), 1 GB/oy Shimoliy Amerikadan chiquvchi trafik
  (bu bot oyiga bir necha MB ishlatadi)
- Ro'yxatdan o'tishda **bank kartasi** kerak. Yangi akkaunt $300 / 90 kun
  bonus oladi, lekin `e2-micro` bonus tugagach ham bepul qoladi.

> ⚠️ Kutilmagan to'lovdan saqlanish uchun **Budget alert** ($1) qo'ying
> (1-qadam). `e2-micro` + 30 GB standart disk doirasida hisob $0 bo'ladi.

## 1. Akkaunt va billing (brauzerda, bir marta)

1. <https://console.cloud.google.com> — Google akkaunt bilan kiring.
2. **Billing → Create account** → karta qo'shing.
3. **Billing → Budgets & alerts → Create budget** → miqdor `1`, 50/90/100%
   xabarnoma. (Ixtiyoriy, lekin tavsiya.)
4. Loyiha: "My First Project" yetadi, yoki **Create project**
   (masalan `arab-vocab-bot`).

## 2. `gcloud` bilan kirish (o'zingizning kompyuter/Termux'ingizda)

```bash
gcloud auth login
gcloud config set project <PROJECT_ID>
gcloud services enable compute.googleapis.com
```

## 3. VM yaratish

```bash
gcloud compute instances create arab-vocab-bot \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard
```

## 4. Kodni ko'chirish

Telefondagi progress yo'qolmasligi uchun **`words.db` ni ham** yuboramiz.
Avval telefondagi botni to'xtating (`Ctrl+C`) — bitta token bilan ikki
instansiya polling qilsa Telegram `Conflict` xatosi beradi.

```bash
gcloud compute scp --recurse --zone=us-central1-a \
  ./arab-uzbek-vocab arab-vocab-bot:~/
```

## 5. O'rnatish (VM ichida)

```bash
gcloud compute ssh arab-vocab-bot --zone=us-central1-a
```

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv
cd ~/arab-uzbek-vocab
python3 -m venv venv
venv/bin/pip install -r requirements.txt
# .env allaqachon ko'chirilgan (TELEGRAM_BOT_TOKEN ichida). Tekshiring: cat .env
# words.db allaqachon ko'chirilgan bo'lsa, parse_pdf.py qayta ishga tushirish shart emas
venv/bin/python bot.py     # "Bot ishga tushdi (polling)" -> Ctrl+C
```

## 6. systemd xizmati (avtorestart + reboot'da avtostart)

```bash
sudo cp deploy/arab-vocab-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/arab-vocab-bot.service
#   User=<sizning-login>   (gcloud SSH login, `whoami`)
#   WorkingDirectory=/home/<login>/arab-uzbek-vocab
#   EnvironmentFile=/home/<login>/arab-uzbek-vocab/.env
#   ExecStart=/home/<login>/arab-uzbek-vocab/venv/bin/python bot.py

sudo systemctl daemon-reload
sudo systemctl enable --now arab-vocab-bot
systemctl status arab-vocab-bot
journalctl -u arab-vocab-bot -f
```

## 7. Yangilash

```bash
gcloud compute scp --recurse --zone=us-central1-a \
  ./arab-uzbek-vocab/bot.py ./arab-uzbek-vocab/database.py \
  arab-vocab-bot:~/arab-uzbek-vocab/
gcloud compute ssh arab-vocab-bot --zone=us-central1-a --command \
  'sudo systemctl restart arab-vocab-bot'
```

`words.db` VM'da `WorkingDirectory` ichida — yangilashda tegmang. Zaxira:

```bash
gcloud compute scp --zone=us-central1-a \
  arab-vocab-bot:~/arab-uzbek-vocab/words.db ./words.db.backup
```

## VM boshqaruvi

```bash
gcloud compute instances stop arab-vocab-bot  --zone=us-central1-a   # to'xtatish
gcloud compute instances start arab-vocab-bot --zone=us-central1-a  # yoqish
gcloud compute instances delete arab-vocab-bot --zone=us-central1-a # o'chirish
```
