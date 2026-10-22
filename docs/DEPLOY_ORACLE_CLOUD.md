# Deploy Mascot lên Oracle Cloud Always Free

Chạy toàn bộ Mascot (PostgreSQL, FastAPI, React) trên **một máy ảo Linux luôn bật**,
miễn phí, không cold start. Máy ảo thuộc Oracle Cloud, không phụ thuộc laptop.

```text
Trình duyệt ──HTTPS──► Caddy (cổng 443: chứng chỉ Let's Encrypt, file React, proxy /api)
                          └──► FastAPI (nội bộ, 1 worker) ──► PostgreSQL 16 (nội bộ, volume bền)
```

- Chỉ Caddy mở cổng ra Internet (80, 443). PostgreSQL và FastAPI không public.
- Frontend gọi API cùng tên miền (`/api/v1`), không cần CORS chéo domain.
- Cấu hình nằm trong [`deploy/`](../deploy): `docker-compose.prod.yml`, `Caddyfile`,
  `web.Dockerfile`, `.env.example`, `backup.sh`. Bộ này đã chạy thử local với
  `DOMAIN=localhost`: HTTPS, SPA fallback, proxy API, 14 migration, đăng ký/đăng nhập,
  backup và đọc lại backup đều đạt.

## Vì sao chọn Oracle Cloud

| Nhà cung cấp | Máy miễn phí lâu dài | Ghi chú |
|---|---|---|
| **Oracle Cloud Always Free** | Ampere A1 (ARM), theo hạn mức hiện tại tương đương 2 OCPU / 12 GB RAM, 200 GB đĩa | Mạnh nhất. Dư sức chạy DB + backend + frontend. |
| Google Cloud Free Tier | 1 máy e2-micro: 2 vCPU chia sẻ, 1 GB RAM, 30 GB đĩa, chỉ ở vài region Mỹ | 1 GB RAM rất chật cho PostgreSQL + FastAPI. Chỉ free 1 GB dữ liệu ra/tháng, vượt sẽ tính tiền. |
| AWS Free Tier | Không còn máy free lâu dài cho tài khoản mới (gói mới là credit, hết hạn sau 6 tháng) | Hết thời hạn phải nâng cấp trả phí. |

Số liệu thay đổi theo thời gian; kiểm tra lại trang Free Tier của nhà cung cấp và nhãn
**Always Free** trong console trước khi tạo máy.

**Lưu ý về Oracle:** đăng ký cần thẻ để xác minh (có thể giữ tạm một khoản nhỏ rồi hoàn).
Không nâng cấp tài khoản nếu không muốn bị tính phí. Oracle có thể thu hồi máy Always Free
bị coi là nhàn rỗi trong thời gian dài, và home region đôi khi báo hết máy (out of capacity).

---

## Bước 1. Đăng ký và tạo máy ảo (bạn tự làm trên web Oracle)

1. Đăng ký tại [oracle.com/cloud/free](https://www.oracle.com/cloud/free/). Chọn
   **Home Region** gần Việt Nam (ví dụ Singapore). Home region không đổi được về sau.
2. Trên Windows, tạo SSH key (PowerShell):
   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\oracle_mascot
   ```
   Giữ kín file `oracle_mascot`; chỉ upload file `oracle_mascot.pub`.
3. Console → **Compute → Instances → Create instance**:
   - **Image:** Oracle Linux 9.
   - **Shape:** `VM.Standard.A1.Flex` (Ampere), 2 OCPU, 12 GB RAM. Phải có nhãn *Always Free eligible*.
   - **Networking:** để mặc định, bật *Assign a public IPv4 address*.
   - **SSH keys:** upload `oracle_mascot.pub`.
   - **Boot volume:** 50 GB là đủ.
   - Nếu báo *Out of capacity*: thử lại sau vài giờ, đổi availability domain, hoặc giảm còn 1 OCPU / 6 GB.
4. Ghi lại **Public IP** của máy.

## Bước 2. Mở cổng 80 và 443

1. Console → máy ảo → **Subnet → Security List → Add Ingress Rules**:
   - Source `0.0.0.0/0`, TCP, destination port `80`.
   - Source `0.0.0.0/0`, TCP, destination port `443`.
2. Không mở cổng 5432 (PostgreSQL) hay 8000 (FastAPI).

## Bước 3. Tên miền miễn phí

Caddy cần một tên miền để lấy chứng chỉ HTTPS. Dùng [DuckDNS](https://www.duckdns.org)
(miễn phí): đăng nhập, tạo subdomain (ví dụ `mascot-dat`), điền **Public IP** của máy ảo
vào ô *current ip*. Tên miền sẽ là `mascot-dat.duckdns.org`.

Kiểm tra từ Windows: `nslookup mascot-dat.duckdns.org` phải trả về đúng Public IP.

## Bước 4. Cài Docker trên máy ảo

```powershell
ssh -i $HOME\.ssh\oracle_mascot opc@<PUBLIC_IP>
```

Trên máy ảo:

```bash
sudo dnf -y update
sudo dnf -y install git dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker opc

# Firewall trong máy (ngoài Security List ở Bước 2)
sudo firewall-cmd --permanent --add-service=http --add-service=https
sudo firewall-cmd --permanent --add-port=443/udp
sudo firewall-cmd --reload

exit   # đăng nhập lại để quyền docker có hiệu lực
```

## Bước 5. Lấy code và cấu hình

```bash
ssh -i ~/.ssh/oracle_mascot opc@<PUBLIC_IP>
git clone https://github.com/cupeedrl/Mascot.git
cd Mascot
cp deploy/.env.example deploy/.env
openssl rand -hex 24   # dùng làm POSTGRES_PASSWORD
openssl rand -hex 32   # dùng làm JWT_SECRET_KEY
nano deploy/.env
```

Điền: `DOMAIN` (tên DuckDNS), `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `GROQ_API_KEY`,
và cấu hình email nếu cần gửi mail đặt lại mật khẩu. `deploy/.env` không bao giờ được
commit (đã nằm trong `.gitignore`).

```bash
chmod 600 deploy/.env
```

## Bước 6. Chạy

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
docker compose -f deploy/docker-compose.prod.yml ps
docker compose -f deploy/docker-compose.prod.yml logs -f web backend
```

Lần đầu build mất vài phút (máy ARM tự build image). Backend tự chạy
`alembic upgrade head` trước khi khởi động, nên database mới có sẵn catalog CEFR/HSK.

Kiểm tra:

- `https://<DOMAIN>/api/v1/health` trả về `{"status":"ok"}`.
- `https://<DOMAIN>/api/v1/health/database` trả về `"database":"reachable"`.
- `https://<DOMAIN>` mở được giao diện, đăng ký và đăng nhập được.

Cấp quyền admin cho tài khoản đã đăng ký (image production không chứa `scripts/`,
nên mount thư mục này vào lúc chạy):

```bash
docker compose -f deploy/docker-compose.prod.yml run --rm --no-deps \
  -v "$PWD/backend/scripts:/app/scripts:ro" backend python scripts/set_admin.py <email>
```

## Bước 7. Backup hằng ngày

```bash
chmod +x deploy/backup.sh
./deploy/backup.sh                     # chạy thử
crontab -e
# thêm dòng sau (backup 03:00 mỗi ngày, giữ 7 bản mới nhất):
0 3 * * * /home/opc/Mascot/deploy/backup.sh >> /home/opc/mascot-backups/backup.log 2>&1
```

Backup nằm trên chính máy ảo. Thỉnh thoảng tải một bản về máy khác:
`scp -i $HOME\.ssh\oracle_mascot opc@<PUBLIC_IP>:mascot-backups/<file>.dump .`

## (Tùy chọn) Chuyển dữ liệu từ Neon

Chỉ cần nếu muốn giữ tài khoản và từ vựng đang có trên bản Render/Neon.

1. Xem phiên bản PostgreSQL của Neon (Neon console → project → Settings). Dùng image
   `postgres:<cùng phiên bản>` để dump. Nếu Neon là 17 thì đổi `db` trong compose
   sang `postgres:17-alpine` **trước lần chạy đầu tiên**, để restore không lỗi phiên bản.
2. Dump từ Neon (connection string lấy trong Neon console, không commit, không dán vào chat):
   ```bash
   read -rs NEON_URL   # dán connection string rồi Enter
   docker run --rm -e NEON_URL postgres:16-alpine sh -c 'pg_dump "$NEON_URL" -Fc --no-owner' > neon.dump
   unset NEON_URL
   ```
3. Restore vào DB mới (dừng backend để không ai ghi trong lúc restore):
   ```bash
   docker compose -f deploy/docker-compose.prod.yml stop backend
   docker compose -f deploy/docker-compose.prod.yml exec -T db \
     sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < neon.dump
   docker compose -f deploy/docker-compose.prod.yml start backend
   ```
4. Đăng nhập thử bằng tài khoản cũ, kiểm tra từ vựng, ôn tập, chatbot rồi mới đổi link.
   Xóa `neon.dump` khi xong, vì nó chứa dữ liệu người dùng.

## Cập nhật phiên bản mới

```bash
cd ~/Mascot
git pull
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Migration mới chạy tự động khi backend khởi động lại.

## Sau khi chạy ổn

- Đổi link Live demo trong README và CV sang `https://<DOMAIN>`.
- Có thể giữ bản Vercel + Render làm dự phòng, hoặc tắt đi.
- Bảo trì định kỳ: `sudo dnf -y update` rồi khởi động lại máy khi có cập nhật kernel.

## Xử lý sự cố

| Triệu chứng | Kiểm tra |
|---|---|
| Không mở được `https://<DOMAIN>` | DNS đã trỏ đúng IP chưa (`nslookup`); Security List và `firewall-cmd` đã mở 80/443 chưa; `docker compose ... logs web` có lỗi lấy chứng chỉ không. |
| Trang mở nhưng API lỗi 502 | `docker compose ... logs backend`: thường do thiếu biến trong `deploy/.env` (ví dụ `JWT_SECRET_KEY` ngắn hơn 32 ký tự). |
| Chatbot báo "AI đang bận" | Groq free bị giới hạn request/phút. Xem trang Admin → AI Usage. |
| Hết dung lượng đĩa | `docker system prune` để xóa image cũ; kiểm tra thư mục `~/mascot-backups`. |
