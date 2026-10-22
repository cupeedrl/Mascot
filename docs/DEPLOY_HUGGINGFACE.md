# Deploy backend Mascot lên Hugging Face Spaces (miễn phí, không cần thẻ)

Mục tiêu: bỏ cold start 30–50 giây của Render free mà không cần thẻ và không sửa code.

```text
Trình duyệt ──► Vercel (React, như cũ)
                   └──HTTPS──► Hugging Face Space (FastAPI, Docker) ──► Neon PostgreSQL (như cũ)
```

| | Render free (hiện tại) | Hugging Face Space free |
|---|---|---|
| Phần cứng | Rất yếu (~512 MB RAM) | **2 vCPU, 16 GB RAM** |
| Khi nào ngủ | Sau **15 phút** không có truy cập | Sau **48 giờ** không có truy cập |
| Cần thẻ | Không | Không |
| Code phải sửa | — | Không |

Vì Space chỉ ngủ sau 48 giờ, chỉ cần có người dùng hoặc một lịch ping mỗi ngày là backend
luôn thức. Các con số lấy theo tài liệu Hugging Face tại thời điểm viết; kiểm tra lại
trong trang Settings của Space.

Cấu hình nằm trong [`deploy/huggingface/`](../deploy/huggingface): `Dockerfile` và
`README.md`. Dockerfile tự clone backend từ GitHub (`cupeedrl/Mascot`, nhánh `main`)
khi build, chạy migration rồi khởi động Uvicorn ở cổng 7860 bằng user 1000.

Đã chạy thử image local: health và health/database trả 200, chạy bằng user 1000, chế độ
production tắt `/docs`, CORS chỉ nhận đúng origin Vercel (origin lạ bị từ chối), đăng nhập,
dashboard và chatbot gọi tool đều hoạt động.

**Lưu ý:** Space phải để **Public** thì Vercel mới gọi được API. Code của Space là public
(giống repo GitHub), còn secret trong Settings thì chỉ chủ Space thấy.

---

## Bước 1. Tạo tài khoản và Space

1. Đăng ký tại [huggingface.co/join](https://huggingface.co/join) (chỉ cần email), xác minh email.
2. Vào [huggingface.co/new-space](https://huggingface.co/new-space):
   - **Space name:** `mascot-api`
   - **License:** để trống hoặc `mit`
   - **Select the Space SDK:** **Docker** → template **Blank**
   - **Space hardware:** **CPU basic · 2 vCPU · 16 GB · FREE**
   - **Visibility:** **Public**
   - Bấm **Create Space**.

## Bước 2. Đưa 2 file cấu hình lên Space

1. Trong Space vừa tạo, mở tab **Files** → **Add file** → **Upload files**.
2. Kéo thả 2 file từ máy: `deploy/huggingface/Dockerfile` và `deploy/huggingface/README.md`.
   File `README.md` có sẵn của Space sẽ bị thay thế; đó là điều mong muốn (nó khai báo
   `sdk: docker` và `app_port: 7860`).
3. Bấm **Commit changes to main**. Space bắt đầu build; **chưa cần quan tâm lỗi** cho tới khi
   điền xong secret ở Bước 3.

## Bước 3. Điền biến môi trường

Space → **Settings** → mục **Variables and secrets** → **New secret** cho từng dòng.

Giá trị lấy ở [Render Dashboard](https://dashboard.render.com) → service backend Mascot →
**Environment**: copy đúng giá trị đang dùng, **không để dấu cách thừa ở đầu hoặc cuối**.

| Tên | Giá trị |
|---|---|
| `DATABASE_URL` | Giống Render (dạng `postgresql+psycopg://...neon.tech/...`) |
| `JWT_SECRET_KEY` | Giống Render, để người đang đăng nhập không bị đăng xuất |
| `GROQ_API_KEY` | Key Groq của bạn |
| `CORS_ORIGINS` | `["https://mascot-ai-learn.vercel.app"]` |
| `FRONTEND_BASE_URL` | `https://mascot-ai-learn.vercel.app` |
| `EMAIL_PROVIDER` | Giống Render (`brevo`, `resend`, `gmail_smtp` hoặc `console`) |
| `EMAIL_FROM` | Giống Render |
| `BREVO_API_KEY` / `RESEND_API_KEY` / `SMTP_USERNAME` + `SMTP_APP_PASSWORD` | Chỉ key của provider đang dùng, giống Render |

Các biến khác (`AI_PROVIDER`, model, giới hạn tool...) có giá trị mặc định trong code;
chỉ thêm nếu trên Render bạn đã đổi chúng.

Sau khi thêm secret: **Settings → Factory rebuild** (hoặc **Restart this Space**).

## Bước 4. Kiểm tra backend

1. Tab **Logs** của Space: chờ tới dòng `Uvicorn running on http://0.0.0.0:7860`.
   Nếu thấy lỗi cấu hình, thường là thiếu hoặc sai một secret ở Bước 3.
2. Địa chỉ API có dạng `https://<username>-mascot-api.hf.space` (xem chính xác ở menu **⋮ →
   Embed this Space → Direct URL**). Mở:
   - `https://<username>-mascot-api.hf.space/api/v1/health` → `{"status":"ok"}`
   - `https://<username>-mascot-api.hf.space/api/v1/health/database` → `"database":"reachable"`

## Bước 5. Cho Vercel gọi API mới

1. [Vercel Dashboard](https://vercel.com/dashboard) → project Mascot → **Settings → Environment Variables**.
2. Sửa `VITE_API_BASE_URL` (môi trường **Production**) thành
   `https://<username>-mascot-api.hf.space/api/v1`.
3. **Deployments** → bản mới nhất → **⋯ → Redeploy**. Biến `VITE_*` được gắn vào lúc build,
   nên bắt buộc phải redeploy.
4. Mở `https://mascot-ai-learn.vercel.app`, đăng nhập, thử ôn tập và chatbot.

Render có thể giữ làm dự phòng: đổi lại `VITE_API_BASE_URL` và redeploy là quay về.
Nếu không dùng nữa, vào Render → service → **Settings → Suspend** để không ai ghi vào DB
từ hai nơi.

## Bước 6. Giữ Space luôn thức (tùy chọn)

Space ngủ sau 48 giờ không có truy cập. Nếu có lúc không ai dùng tới 2 ngày, tạo lịch ping
miễn phí tại [cron-job.org](https://cron-job.org) (không cần thẻ):

- **URL:** `https://<username>-mascot-api.hf.space/api/v1/health`
- **Schedule:** mỗi 12 giờ
- Ping `/api/v1/health` (không chạm database) để không tốn giờ compute của Neon.

## Cập nhật phiên bản mới

Push code lên nhánh `main` của GitHub → Space → **Settings → Factory rebuild**. Dockerfile
tự lấy commit mới nhất; migration chạy khi backend khởi động.

## Xử lý sự cố

| Triệu chứng | Kiểm tra |
|---|---|
| Build lỗi ở bước tải code GitHub (404) | Repo `cupeedrl/Mascot` phải đang **public**. |
| Log báo lỗi validation khi khởi động | Thiếu secret bắt buộc (`DATABASE_URL`, `JWT_SECRET_KEY` ≥ 32 ký tự) hoặc secret email không khớp `EMAIL_PROVIDER`. |
| Chatbot báo không tạo được phản hồi, log Groq `401 Invalid API Key` | `GROQ_API_KEY` sai hoặc có dấu cách thừa. |
| Trình duyệt báo lỗi CORS | `CORS_ORIGINS` phải đúng `["https://mascot-ai-learn.vercel.app"]`, không có `/` ở cuối. |
| Lần đầu mở sau lâu không dùng vẫn chậm | Space đã ngủ quá 48 giờ; dùng lịch ping ở Bước 6. |
