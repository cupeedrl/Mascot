# Mascot

Mascot là hệ thống quản lý học ngôn ngữ. Dự án hiện đã hoàn thành **Phase 8 — Dashboard** cho General English:

- React, TypeScript và Vite.
- FastAPI, SQLAlchemy, Pydantic và Alembic.
- PostgreSQL chạy bằng Docker Compose.
- Đăng ký, đăng nhập, đăng xuất và JWT access token.
- Catalog English / General English.
- Thư viện dùng chung gồm các vocabulary set/entry demo theo CEFR và chủ đề.
- Luồng Learn cho phép chọn một, nhiều hoặc toàn bộ từ và đưa vào My Vocabulary.
- Vocabulary CRUD, tìm kiếm, lọc và phân trang theo từng người dùng.
- Vocabulary Review tự đánh giá với lịch cố định, bộ đếm và trạng thái học theo từng người dùng.
- AI Vocabulary Assistant tạo bản nháp có cấu trúc để người dùng xem, sửa và chủ động lưu.
- Practice hỗ trợ multiple choice và fill in the blank, chấm hoàn toàn bằng backend và lưu attempt history.
- AI Exercise Generator dùng Groq tạo bài tập có cấu trúc từ My Vocabulary, kiểm tra toàn bộ output trước khi lưu và chuyển ngay sang Practice.
- Dashboard tổng hợp vocabulary, từ đến hạn, attempts, accuracy và từ mới thêm hoàn toàn từ PostgreSQL.

Basic AI Tutor đã được chuyển sang phạm vi Future/Optional.

## Kiến trúc

```text
React + TypeScript + Vite (http://localhost:5173)
                |
                | REST /api/v1
                | Authorization: Bearer <JWT>
                v
FastAPI + SQLAlchemy (http://localhost:8000)
                |
                v
PostgreSQL (localhost:5432)
```

Backend lấy danh tính người dùng từ JWT. Request Vocabulary không nhận `user_id`; mọi truy vấn dữ liệu sở hữu đều lọc đồng thời bằng `vocabulary.id` và `current_user.id`.

## Yêu cầu hệ thống

- Docker Desktop và Docker Compose v2.
- Nếu chạy ứng dụng trực tiếp trên Windows:
  - Python 3.11–3.14.
  - Node.js 22.12 trở lên và npm.
- DBeaver là tùy chọn để xem PostgreSQL.

## Cấu hình môi trường

Từ thư mục gốc:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

Đổi `POSTGRES_PASSWORD` trong `.env` gốc và mật khẩu trong `DATABASE_URL` tại `backend/.env` sao cho khớp nhau.

Tạo JWT secret ngẫu nhiên:

```powershell
$bytes = New-Object byte[] 48
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
[Convert]::ToBase64String($bytes)
```

Chép kết quả vào `JWT_SECRET_KEY` trong `.env` gốc và `backend/.env`. Không commit file `.env`; các giá trị trong `.env.example` chỉ là placeholder.

Để dùng AI Vocabulary Assistant với cấu hình mặc định, tạo Groq API key tại <https://console.groq.com/keys> và đặt nó **chỉ ở backend**:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=your-real-groq-key-here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_BASE_URL=https://api.groq.com/openai/v1
AI_REQUEST_TIMEOUT_SECONDS=20
AI_MAX_OUTPUT_TOKENS=800
AI_EXERCISE_MAX_OUTPUT_TOKENS=4000
```

Groq Free Plan có giới hạn request/token và có thể thay đổi theo chính sách của Groq; đây không phải tài nguyên không giới hạn. Mascot dùng model open-weight `openai/gpt-oss-20b` được Groq host, không chạy model trên máy local.

Khi chạy Docker Compose, đặt các biến trên trong `.env` gốc. Khi chạy backend trực tiếp, đặt chúng trong `backend/.env`. Không thêm `VITE_` vào tên API key và không đặt key trong `frontend/.env`; biến có tiền tố `VITE_` có thể được đưa vào bundle trình duyệt.

Adapter OpenAI cũ vẫn là lựa chọn dự phòng. Khi muốn dùng lại, đặt `AI_PROVIDER=openai`, `OPENAI_API_KEY` và `OPENAI_MODEL`. Mỗi lần chỉ có một provider được chọn; V1 không tự động failover giữa Groq và OpenAI.

### Cấu hình Email & Đặt lại mật khẩu (Phase F & F.2)

Mascot hỗ trợ gửi email khôi phục mật khẩu thông qua **Gmail SMTP** (phù hợp gửi thực tế không cần custom domain), **Resend** (API), hoặc **Console/Log** (local development):

#### 1. Cấu hình Gmail SMTP (Khuyến nghị cho Production nhỏ / Demo)

1. Tạo hoặc dùng tài khoản Gmail dành cho Mascot.
2. Bật **Xác minh 2 bước (2-Step Verification)** trong tài khoản Google.
3. Truy cập <https://myaccount.google.com/apppasswords>, tạo **Mật khẩu ứng dụng (App Password)** cho Mascot (chuỗi 16 ký tự).
4. Cấu hình biến môi trường trên Render:

```dotenv
EMAIL_PROVIDER=gmail_smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_APP_PASSWORD=abcd-efgh-ijkl-mnop
EMAIL_FROM=Mascot <your-email@gmail.com>
FRONTEND_BASE_URL=https://your-mascot-app.vercel.app
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=20
```

#### 2. Cấu hình Resend (Tùy chọn)

```dotenv
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_your_resend_api_key_here
EMAIL_FROM=Mascot <onboarding@resend.dev> # hoặc domain đã verify
FRONTEND_BASE_URL=https://your-mascot-app.vercel.app
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=20
```

#### 3. Local Development

```dotenv
EMAIL_PROVIDER=console
FRONTEND_BASE_URL=http://localhost:5173
```
Link đặt lại mật khẩu sẽ được in trực tiếp ra terminal khi có yêu cầu quên mật khẩu.

### Quản trị hệ thống (Phase G1)

Mascot hỗ trợ phân quyền người dùng thông qua cột `role` (`"user"` hoặc `"admin"`):

- **Người dùng thông thường (`user`)**: Toàn quyền học tập, ôn tập, sổ tay cá nhân. Không truy cập được route `/admin` hoặc API `/api/v1/admin/*`.
- **Quản trị viên (`admin`)**: Truy cập được giao diện quản trị `/admin` và gọi các API bảo mật của admin.
- **Bảo mật**: Phân quyền được kiểm tra nghiêm ngặt tại backend qua dependency `require_admin` (trả về 403 Forbidden nếu không đủ quyền).

#### Cách gán quyền Admin cho tài khoản:

Sử dụng script CLI đi kèm:

```bash
# Trên máy dev hoặc console của Render:
python scripts/set_admin.py <email_can_gan_quyen>
```

Hoặc qua SQL trực tiếp trên Neon PostgreSQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your-admin-email@example.com';
```

Sau khi gán quyền, đăng nhập lại hoặc tải lại trang, tài khoản sẽ truy cập được đường dẫn `/admin`.



## Chạy toàn bộ bằng Docker Compose

```powershell
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
docker compose ps
```

Truy cập:

- Frontend: <http://localhost:5173>
- Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>
- Database health: <http://localhost:8000/api/v1/health/database>

Dừng ứng dụng nhưng giữ dữ liệu:

```powershell
docker compose down
```

Không chạy `docker compose down -v` trừ khi chủ động muốn xóa volume và toàn bộ dữ liệu local.

Khi dependency backend thay đổi:

```powershell
docker compose up -d --build backend
```

Khi dependency frontend thay đổi:

```powershell
docker compose exec frontend npm install
docker compose restart frontend
```

## Chạy trực tiếp trên Windows

### PostgreSQL

```powershell
docker compose up -d db
docker compose ps db
```

### Backend

```powershell
Set-Location backend
python -m venv --clear .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

Mở terminal thứ hai:

```powershell
Set-Location frontend
npm ci
npm run dev
```

## Authentication

| Method | Endpoint | Mục đích |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Tạo tài khoản; mật khẩu được băm bằng Argon2id. |
| `POST` | `/api/v1/auth/login` | Trả JWT access token. |
| `GET` | `/api/v1/auth/me` | Trả người dùng hiện tại từ JWT. |
| `POST` | `/api/v1/auth/logout` | Logout stateless; frontend xóa token khỏi bộ nhớ. |

Frontend giữ access token trong bộ nhớ React và gửi:

```http
Authorization: Bearer <access_token>
```

Token không được lưu vào `localStorage`, vì vậy refresh trang sẽ yêu cầu đăng nhập lại trong V1.

## Catalog General English

Migration `20260814_0002` tạo và seed duy nhất:

- Language: `en` / `English`.
- Learning track: `general-english` / `General English`, framework `CEFR`.

Không seed IELTS, TOEIC, Chinese hoặc HSK. Frontend gọi catalog API để lấy UUID, không hardcode ID:

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/catalog/languages` | Danh sách language đang hoạt động. |
| `GET` | `/api/v1/catalog/learning-tracks?language_code=en` | Danh sách track đang hoạt động. |

Hai endpoint đều yêu cầu JWT.

## Mascot Vocabulary Library

Migration `20260814_0003` tạo `vocabulary_sets`, `vocabulary_entries`, thêm nullable `source_vocabulary_entry_id` vào `vocabularies`, và seed 8 bộ demo với 40 từ đại diện:

- A1: Daily Life, Family.
- A2: Travel, Work.
- B1: Education, Communication.
- B2: Work & Business, Technology.

Đây là dữ liệu demo để phát triển, không phải từ điển CEFR chính thức hoặc đầy đủ. C1/C2 đã có trong UI/framework nhưng chưa seed nội dung.

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/vocabulary-sets` | List/filter theo `language`, `learning_track`, `level`, `topic`. |
| `GET` | `/api/v1/vocabulary-sets/{id}` | Chi tiết set và entries, kèm trạng thái đã thêm theo user. |
| `POST` | `/api/v1/vocabulary-entries/{id}/add-to-my-vocabulary` | Thêm một entry. |
| `POST` | `/api/v1/vocabulary-entries/import` | Thêm nhiều entry đã chọn. |
| `POST` | `/api/v1/vocabulary-sets/{id}/start-learning` | Thêm toàn bộ set. |

Catalog không có `user_id` và chỉ đọc qua các API trên. Import tạo bản ghi thuộc người dùng hiện tại với status `new` và giữ nguồn. Unique index có điều kiện chống import trùng cùng entry cho cùng user; import lặp trả created/skipped counts thay vì tạo bản sao. Manual vocabulary có source null nên vẫn được phép trùng từ/nghĩa.

Không dùng `user_vocabulary_sets`: trạng thái chưa thêm/đã thêm một phần/toàn bộ được suy ra trực tiếp từ source entry của My Vocabulary.

## Vocabulary API

| Method | Endpoint | Mục đích |
|---|---|---|
| `POST` | `/api/v1/vocabularies` | Tạo từ vựng thuộc người dùng hiện tại. |
| `GET` | `/api/v1/vocabularies` | Danh sách, tìm kiếm, lọc và phân trang. |
| `GET` | `/api/v1/vocabularies/{id}` | Xem một từ thuộc người dùng hiện tại. |
| `PATCH` | `/api/v1/vocabularies/{id}` | Cập nhật các trường được phép. |
| `DELETE` | `/api/v1/vocabularies/{id}` | Xóa từ thuộc người dùng hiện tại, trả `204`. |

## Vocabulary Review

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/vocabularies/due-for-review?limit=50` | Lấy các từ đến hạn của người dùng hiện tại. |
| `POST` | `/api/v1/vocabularies/{id}/reviews` | Gửi `{"is_correct": true/false}` và cập nhật tiến độ trong một transaction. |

Một từ chưa `mastered` được coi là đến hạn khi `next_review_at` bằng `NULL` hoặc nhỏ hơn/bằng thời điểm hiện tại. Quy tắc V1:

- Đúng khi `new`: chuyển `learning`, hẹn lại sau 1 ngày.
- Đúng khi `learning`: chuyển `review`, hẹn lại sau 3 ngày.
- Đúng khi `review`: chuyển `mastered`, không còn lịch tiếp theo.
- Sai ở bất kỳ trạng thái đến hạn nào: chuyển về `learning`, hẹn lại sau 1 giờ.

Mỗi lần submit tăng `review_count`, tăng đúng một trong `correct_count`/`incorrect_count`, và cập nhật `last_reviewed_at`. Backend không chấp nhận review sớm, review từ đã mastered, hoặc vocabulary của user khác.

## Exercise System

Phase 6 hỗ trợ hai loại bài tập thuộc từng người dùng:

- `multiple_choice`: người dùng gửi option ID; backend trim, đổi sang chữ hoa và so sánh với option ID chuẩn.
- `fill_in_blank`: backend chuẩn hóa Unicode NFKC, trim, gộp khoảng trắng và so sánh không phân biệt hoa/thường với `correct_answer` và `accepted_answers`.

Không có lời gọi Groq trong quá trình chấm. Mỗi lần nộp tạo một `exercise_attempts` bất biến và chép đáp án đúng vào cột `correct_answer` như một snapshot lịch sử.

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/exercises` | List/phân trang bài tập của current user; có filter `exercise_type` và `learning_track_id`. |
| `GET` | `/api/v1/exercises/{id}` | Trả bài tập learner-safe, không có answer key, explanation hoặc source vocabulary IDs. |
| `POST` | `/api/v1/exercises/{id}/attempts` | Chấm xác định, lưu attempt, sau đó mới trả đáp án và explanation. |
| `GET` | `/api/v1/exercise-attempts` | List lịch sử attempt của current user. |

`exercises` không lưu `language_id`; language được suy ra qua `learning_track_id` để tránh hai nguồn dữ liệu có thể mâu thuẫn. `exercise_vocabularies` liên kết bài tập với các bản ghi My Vocabulary bằng foreign key. Trường `source` dùng `manual` cho bài demo Phase 6 và `ai` cho bài do Phase 7 sinh.

Sau khi tài khoản đã có ít nhất một từ trong My Vocabulary, tạo tối đa hai bài demo idempotent:

```powershell
docker compose exec backend python -m scripts.seed_demo_exercises --email learner@example.com
```

Một từ đủ tạo fill-in-the-blank; cần ít nhất bốn từ cùng learning track để tạo thêm multiple-choice. Chạy lại script không tạo trùng cùng prompt.

## AI Exercise Generator

Phase 7 tái sử dụng đúng adapter Groq của AI Vocabulary Assistant; không thêm provider thứ hai và không đưa API key ra frontend.

| Method | Endpoint | Mục đích |
|---|---|---|
| `POST` | `/api/v1/ai/exercises/generate` | Kiểm tra My Vocabulary thuộc current user, gọi Groq, validate rồi lưu nguyên tử một batch bài tập. |

Request mẫu:

```json
{
  "vocabulary_ids": [
    "UUID_1",
    "UUID_2",
    "UUID_3",
    "UUID_4"
  ],
  "exercise_type": "multiple_choice",
  "count": 2
}
```

Giới hạn V1: 1–20 UUID duy nhất, 1–10 câu, và `count` không lớn hơn số từ được chọn. Multiple choice cần ít nhất bốn từ khác nhau; toàn bộ từ trong một request phải cùng learning track.

Luồng backend:

```text
JWT current user
→ kiểm tra quyền sở hữu vocabulary
→ chỉ gửi UUID/word/part of speech/meaning/examples tới Groq
→ Pydantic kiểm tra structured output
→ kiểm tra type/count/options/answer/source UUID/track
→ lưu toàn bộ batch với source=ai trong một transaction
→ trả learner-safe exercises không có đáp án
```

Nếu một ứng viên sai, toàn bộ batch bị từ chối và không có câu nào được lưu. Khi người học nộp đáp án, endpoint Phase 6 chấm bằng code xác định; Groq không được gọi để chấm. Điều này giữ grading ổn định, kiểm thử được và không phát sinh chi phí AI cho mỗi lần submit.

Trang Practice cho phép chọn từng từ hoặc tất cả từ đang có trong My Vocabulary, chọn loại bài và số câu. Nút tạo bị vô hiệu hóa trong khi request đang chạy để tránh double-click. Bài vừa tạo trở thành phiên luyện tập hiện tại ngay sau khi backend xác nhận đã lưu.

## Dashboard

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/v1/dashboard` | Trả số liệu tổng hợp và 5 vocabulary mới nhất của current user; yêu cầu JWT. |

Dashboard không gọi Groq và không có bảng analytics riêng. Backend thực hiện một aggregate query cho vocabulary, một aggregate query cho exercise attempts và một query `ORDER BY created_at DESC, id DESC LIMIT 5` cho danh sách gần đây.

| Metric | Định nghĩa |
|---|---|
| `total_vocabulary` | Tổng số bản ghi My Vocabulary thuộc current user. |
| `new_words` | Vocabulary có `learning_status = 'new'`. |
| `learning_words` | Vocabulary có `learning_status = 'learning'`. |
| `review_words` | Vocabulary có `learning_status = 'review'`. |
| `mastered_words` | Vocabulary có `learning_status = 'mastered'`. |
| `words_due_for_review` | Chưa mastered và `next_review_at` là `NULL` hoặc đã đến hạn. |
| `exercises_completed` | Tổng số lần nộp bài trong `exercise_attempts`; làm lại cùng bài vẫn là một lần hoàn thành mới. |
| `correct_exercise_attempts` | Số attempts có `is_correct = true`. |
| `incorrect_exercise_attempts` | Số attempts có `is_correct = false`. |
| `exercise_accuracy` | `correct / completed × 100`, làm tròn một chữ số; bằng `0.0` khi chưa có attempt. |
| `recently_added_vocabulary` | Tối đa 5 từ thuộc current user, mới nhất trước. |

Response mẫu:

```json
{
  "total_vocabulary": 42,
  "new_words": 10,
  "learning_words": 15,
  "review_words": 8,
  "mastered_words": 9,
  "words_due_for_review": 6,
  "exercises_completed": 25,
  "correct_exercise_attempts": 19,
  "incorrect_exercise_attempts": 6,
  "exercise_accuracy": 76.0,
  "recently_added_vocabulary": []
}
```

## AI Vocabulary Assistant

| Method | Endpoint | Mục đích |
|---|---|---|
| `POST` | `/api/v1/ai/vocabulary` | Nhận một từ và trả bản nháp AI có cấu trúc; yêu cầu JWT. |

Request:

```json
{
  "word": "solely"
}
```

Response hợp lệ:

```json
{
  "word": "solely",
  "part_of_speech": "adverb",
  "definition": "Only and not involving anyone or anything else.",
  "translation": "chỉ, duy nhất",
  "cefr_level": "B2",
  "examples": [
    "The decision was solely hers.",
    "This room is used solely for study."
  ]
}
```

Luồng dữ liệu là: nhập từ → backend gọi Groq qua API tương thích OpenAI → `openai/gpt-oss-20b` trả Structured Output → Pydantic kiểm tra lại → frontend hiển thị bản nháp có thể sửa. Endpoint AI không dùng database session và không lưu dữ liệu. Chỉ khi người dùng bấm **Thêm từ vựng**, frontend mới gọi API Vocabulary hiện có để lưu bản đã kiểm tra/chỉnh sửa.

Backend giới hạn input ở một từ tối đa 80 ký tự, chỉ chấp nhận CEFR A1–C2 và đúng hai câu ví dụ. Mặc định request provider timeout sau 20 giây, không retry tự động và giới hạn 800 output token. Các lỗi cấu hình/provider/output được đổi thành lỗi ứng dụng an toàn; key, nội dung xác thực và stack trace không được trả về frontend.

Ví dụ tạo từ:

```json
{
  "learning_track_id": "UUID_FROM_LEARNING_TRACKS_API",
  "word": "Solely",
  "part_of_speech": "adverb",
  "meaning": "Only and not involving anyone or anything else.",
  "translation": "chỉ, duy nhất",
  "translation_language_code": "vi",
  "example_sentences": [
    "The decision was solely hers."
  ],
  "level_code": "B2",
  "topic": "Work",
  "learning_status": "new"
}
```

Backend tự tạo `normalized_word` bằng cách trim, Unicode NFKC và case-fold. Ví dụ `"  Solely  "` được lưu hiển thị là `"Solely"`, còn `normalized_word` là `"solely"`.

Các trường `user_id`, review counters, timestamps và ownership không được nhận trong create/update schema.

### Tìm kiếm, lọc và phân trang

```http
GET /api/v1/vocabularies?page=1&page_size=20&q=sole&learning_status=learning&level=B2&topic=Work
```

- `q`: tìm một phần, không phân biệt hoa/thường trong `word`, `normalized_word`, `meaning`, `translation`.
- `learning_status`: `new`, `learning`, `review`, `mastered`.
- `level`: `A1`, `A2`, `B1`, `B2`, `C1`, `C2`.
- `topic`: so khớp chính xác, không phân biệt hoa/thường.
- `learning_track_id`: lọc theo UUID của track nếu cần.
- `page`: bắt đầu từ `1`.
- `page_size`: từ `1` đến `100`, mặc định `20`.

Response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

Count, filter, offset và limit đều chạy trong truy vấn database; backend không tải toàn bộ dữ liệu để phân trang bằng Python.

## Kiểm thử

Backend:

```powershell
Set-Location backend
./.venv/Scripts/python.exe -m pytest
```

Frontend type-check và build:

```powershell
Set-Location frontend
npm run build
```

Nếu Windows chặn cache trong `node_modules/.tmp`, chạy build bằng container:

```powershell
docker compose exec frontend npm run build
```

Backend tests dùng SQLite tạm thời để chạy nhanh. Migration được kiểm tra riêng trên PostgreSQL. Bộ test gồm auth, personal CRUD/IDOR, library list/filter/detail/import/duplicate/cross-user isolation, review due/scheduling/counters/status/ownership, AI Vocabulary với fake provider, lựa chọn/cấu hình adapter Groq, exercise ownership/answer hiding và deterministic grading. Test không gọi API AI thật và không cần `GROQ_API_KEY` hay `OPENAI_API_KEY`.

## Alembic

Chạy từ `backend/`:

```powershell
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic current
./.venv/Scripts/python.exe -m alembic history
```

Không tạo bảng thủ công bằng DBeaver. Alembic là nguồn sự thật cho schema.

## Kiểm thử thủ công trên frontend

1. Mở <http://localhost:5173> và đăng nhập.
2. Chọn **Learn**, lần lượt mở A1/A2/B1/B2 và xem các topic/set.
3. Mở một set, chọn một từ rồi **Thêm từ đã chọn**.
4. Chọn nhiều từ và import; sau đó thử **Bắt đầu học cả bộ**.
5. Xác nhận từ đã thêm chuyển sang trạng thái **Đã thêm** và import lặp không tạo bản sao.
6. Chọn **My Vocabulary** và kiểm tra dòng nguồn như `B2 · Work & Business`.
7. Chọn **Thêm thủ công**; form mở ở route riêng `/app/vocabulary/new`, không còn Home bên dưới.
8. Kiểm tra manual CRUD, search, status/CEFR/topic filter, delete và pagination như Phase 3.
9. Chọn **Review**; xác nhận từ mới xuất hiện trong hàng đợi và nghĩa đang bị ẩn.
10. Chọn **Hiện nghĩa**, sau đó thử **Correct** hoặc **Incorrect** và kiểm tra từ tiếp theo.
11. Hoàn thành hàng đợi, xác nhận màn hình tổng kết số đúng/sai; tải lại Review để kiểm tra từ vừa ôn chưa đến hạn không xuất hiện lại.
12. Mở **My Vocabulary** → **Thêm thủ công**, nhập một từ như `solely`, rồi bấm **Generate with AI**.
13. Xác nhận có loading, sau đó các trường định nghĩa, nghĩa tiếng Việt, CEFR và đúng hai câu ví dụ được điền nhưng danh sách My Vocabulary chưa có bản ghi mới.
14. Sửa ít nhất một trường trong bản nháp, bấm **Thêm từ vựng**, rồi xác nhận bản đã sửa xuất hiện trong My Vocabulary.
15. Thử **Bỏ gợi ý**, input rỗng, token hết hạn và tạm bỏ `GROQ_API_KEY` để kiểm tra các trạng thái lỗi. Sau khi đổi biến môi trường Docker, chạy `docker compose up -d --force-recreate backend`.
16. Đảm bảo tài khoản có ít nhất bốn từ cùng track, rồi chạy `docker compose exec backend python -m scripts.seed_demo_exercises --email EMAIL_DANG_NHAP` (thay placeholder bằng email thật).
17. Chọn **Practice**, làm một câu multiple choice và một câu fill in the blank; thử cả đáp án đúng và sai.
18. Xác nhận đáp án chỉ xuất hiện sau khi bấm **Nộp đáp án**, explanation được hiển thị, nút sang câu tiếp theo hoạt động và cuối phiên có tổng điểm.
19. Trong **Generate Exercise**, chọn ít nhất bốn từ, loại **Multiple choice**, số câu từ 1 đến số từ đã chọn, rồi bấm **Generate with AI**.
20. Trong lúc tạo, xác nhận nút bị khóa và có trạng thái chờ; khi thành công, làm ngay phiên bài vừa tạo.
21. Chuyển sang **Fill in the blank**, chọn ít nhất một từ và tạo lại. Thử cả đáp án khác hoa/thường để xác nhận backend vẫn chấm xác định.
22. Thử chọn dưới bốn từ cho multiple choice, đặt số câu lớn hơn số từ đã chọn, hoặc tạm bỏ `GROQ_API_KEY` để kiểm tra validation và lỗi provider an toàn.
23. Chọn **Home** và đối chiếu các card tổng từ, đang học, mastered, đến hạn, bài đã hoàn thành và accuracy với dữ liệu vừa tạo.
24. Kiểm tra danh sách **Từ vựng mới thêm** có tối đa 5 từ, mới nhất trước, và các shortcut Learn/Review/Practice điều hướng đúng.
25. Đăng nhập bằng một tài khoản mới chưa có dữ liệu; Home phải hiển thị số 0 và empty state thay vì báo lỗi.

Trang xử lý loading, kho trống, không có kết quả, lỗi API, validation, xác nhận xóa và JWT hết hạn.

## Kiểm thử thủ công trên Swagger

1. Mở <http://localhost:8000/docs>.
2. Đăng ký/đăng nhập bằng `/api/v1/auth/register` và `/api/v1/auth/login`.
3. Copy `access_token`, bấm **Authorize**, nhập token.
4. Gọi `GET /api/v1/catalog/learning-tracks?language_code=en`.
5. Gọi `GET /api/v1/vocabulary-sets?level=B2`, sau đó mở một set.
6. Copy entry IDs và thử import một/nhiều/toàn bộ bằng các POST endpoint Library.
7. Gọi `GET /api/v1/vocabularies` để xác nhận source và ownership.
8. Tiếp tục kiểm tra manual list/get/PATCH/DELETE và các filter Phase 3.
9. Gọi `POST /api/v1/ai/vocabulary` với body `{"word":"solely"}`; xác nhận response có CEFR A1–C2 và đúng hai examples.
10. Gọi `GET /api/v1/vocabularies` trước/sau request AI để xác nhận generation không tự tạo bản ghi.
11. Copy 4 vocabulary UUID cùng track và gọi `POST /api/v1/ai/exercises/generate`; xác nhận response không có `correct_answer`, `accepted_answers`, `explanation` hoặc source UUID.
12. Dùng exercise ID vừa nhận để gọi endpoint attempt, xác nhận đáp án/lời giải chỉ xuất hiện sau khi submit.
13. Gọi `GET /api/v1/dashboard`, đối chiếu status counts, due count, attempt totals, accuracy và recent vocabulary.
14. Bỏ authorization và xác nhận tất cả endpoint được bảo vệ trả `401`.

Để kiểm tra IDOR thủ công, tạo hai tài khoản. Dùng tài khoản B gọi get/PATCH/DELETE với UUID item của tài khoản A; cả ba request phải trả `404`.

## DBeaver

| Thiết lập | Giá trị |
|---|---|
| Host | `localhost` |
| Port | `POSTGRES_PORT` trong `.env`, mặc định `5432` |
| Database | `POSTGRES_DB`, giá trị mẫu `mascot` |
| Username | `POSTGRES_USER`, giá trị mẫu `mascot` |
| Password | `POSTGRES_PASSWORD` trong `.env` |
| SSL | Tắt cho local development |

Sau migration, refresh schema `public` → `Tables`. Các câu SQL chỉ để kiểm tra dữ liệu:

```sql
SELECT id, code, name, native_name, is_active
FROM languages
ORDER BY code;

SELECT
    lt.id,
    lt.code,
    lt.name,
    lt.level_framework,
    l.code AS language_code
FROM learning_tracks AS lt
JOIN languages AS l ON l.id = lt.language_id
ORDER BY l.code, lt.code;

SELECT id, learning_track_id, name, level_code, topic, order_index, is_active
FROM vocabulary_sets
ORDER BY level_code, order_index;

SELECT
    ve.id,
    vs.level_code,
    vs.topic,
    ve.word,
    ve.part_of_speech,
    ve.meaning,
    ve.translation,
    ve.example_sentences
FROM vocabulary_entries AS ve
JOIN vocabulary_sets AS vs ON vs.id = ve.vocabulary_set_id
ORDER BY vs.level_code, vs.order_index, ve.order_index;

SELECT
    v.id,
    v.user_id,
    v.source_vocabulary_entry_id,
    v.word,
    v.normalized_word,
    v.part_of_speech,
    v.meaning,
    v.translation,
    v.level_code,
    v.topic,
    v.learning_status,
    v.example_sentences,
    v.created_at,
    v.updated_at
FROM vocabularies AS v
ORDER BY v.created_at DESC;
```

Kiểm tra riêng tiến độ review theo tài khoản:

```sql
SELECT
    u.email,
    v.word,
    v.learning_status,
    v.review_count,
    v.correct_count,
    v.incorrect_count,
    v.last_reviewed_at,
    v.next_review_at,
    (v.learning_status <> 'mastered'
        AND (v.next_review_at IS NULL OR v.next_review_at <= NOW())) AS is_due
FROM vocabularies AS v
JOIN users AS u ON u.id = v.user_id
ORDER BY u.email, v.next_review_at NULLS FIRST, v.created_at;
```

Kiểm tra Exercise System:

```sql
SELECT
    e.id,
    u.email,
    e.exercise_type,
    e.prompt,
    e.options,
    e.correct_answer,
    e.accepted_answers,
    e.explanation,
    e.source,
    e.created_at
FROM exercises AS e
JOIN users AS u ON u.id = e.user_id
ORDER BY e.created_at DESC;

-- Chỉ các bài do Phase 7 tạo.
SELECT
    e.id,
    u.email,
    e.exercise_type,
    e.prompt,
    e.source,
    e.created_at
FROM exercises AS e
JOIN users AS u ON u.id = e.user_id
WHERE e.source = 'ai'
ORDER BY e.created_at DESC;

SELECT
    ev.exercise_id,
    ev.vocabulary_id,
    v.word
FROM exercise_vocabularies AS ev
JOIN vocabularies AS v ON v.id = ev.vocabulary_id
ORDER BY ev.exercise_id, v.word;

SELECT
    ea.id,
    u.email,
    ea.exercise_id,
    ea.user_answer,
    ea.correct_answer AS correct_answer_snapshot,
    ea.is_correct,
    ea.completed_at
FROM exercise_attempts AS ea
JOIN users AS u ON u.id = ea.user_id
ORDER BY ea.completed_at DESC;

-- Thay YOUR_EMAIL bằng email đăng nhập để kiểm tra độc lập Dashboard.
WITH target_user AS (
    SELECT id
    FROM users
    WHERE normalized_email = lower('YOUR_EMAIL')
)
SELECT
    count(*) AS total_vocabulary,
    count(*) FILTER (WHERE v.learning_status = 'new') AS new_words,
    count(*) FILTER (WHERE v.learning_status = 'learning') AS learning_words,
    count(*) FILTER (WHERE v.learning_status = 'review') AS review_words,
    count(*) FILTER (WHERE v.learning_status = 'mastered') AS mastered_words,
    count(*) FILTER (
        WHERE v.learning_status <> 'mastered'
          AND (v.next_review_at IS NULL OR v.next_review_at <= now())
    ) AS words_due_for_review
FROM vocabularies AS v
WHERE v.user_id = (SELECT id FROM target_user);

WITH target_user AS (
    SELECT id
    FROM users
    WHERE normalized_email = lower('YOUR_EMAIL')
)
SELECT
    count(*) AS exercises_completed,
    count(*) FILTER (WHERE ea.is_correct) AS correct_exercise_attempts,
    count(*) FILTER (WHERE NOT ea.is_correct) AS incorrect_exercise_attempts,
    coalesce(
        round(100.0 * count(*) FILTER (WHERE ea.is_correct) / nullif(count(*), 0), 1),
        0.0
    ) AS exercise_accuracy
FROM exercise_attempts AS ea
WHERE ea.user_id = (SELECT id FROM target_user);

WITH target_user AS (
    SELECT id
    FROM users
    WHERE normalized_email = lower('YOUR_EMAIL')
)
SELECT v.id, v.word, v.meaning, v.level_code, v.learning_status, v.created_at
FROM vocabularies AS v
WHERE v.user_id = (SELECT id FROM target_user)
ORDER BY v.created_at DESC, v.id DESC
LIMIT 5;
```

Không chia sẻ hoặc log `password_hash`, JWT hay giá trị secret.

## Hướng dẫn triển khai Production (Neon + Render + Vercel)

### 1. Thứ tự triển khai (Deployment Order)

1. **Bước 1 — Khởi tạo Database (Neon PostgreSQL):**
   - Tạo database instance trên [Neon](https://neon.tech).
   - Lấy chuỗi kết nối dạng: `postgresql+psycopg://<user>:<password>@<ep-xyz>.region.aws.neon.tech/<dbname>?sslmode=require`.

2. **Bước 2 — Chạy Migration khởi tạo schema:**
   - Chạy lệnh migration từ máy phát triển hoặc CI/CD trỏ tới Neon:
     ```bash
     cd backend
     DATABASE_URL="postgresql+psycopg://<user>:<password>@<ep-xyz>.region.aws.neon.tech/<dbname>?sslmode=require" alembic upgrade head
     ```

3. **Bước 3 — Triển khai Backend (Render):**
   - Tạo **Web Service** mới trên [Render](https://render.com) từ repository này.
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -e .`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Cấu hình Environment Variables (xem bảng bên dưới).

4. **Bước 4 — Triển khai Frontend (Vercel):**
   - Import repository trên [Vercel](https://vercel.com).
   - **Root Directory:** `frontend`
   - **Framework Preset:** `Vite`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - Cấu hình biến môi trường: `VITE_API_BASE_URL=https://<your-render-backend>.onrender.com/api/v1`
   - *Lưu ý:* `frontend/vercel.json` tự động cấu hình rewrite cho React Router SPA.

5. **Bước 5 — Cập nhật CORS và Smoke Test:**
   - Sau khi Vercel sinh domain (ví dụ `https://mascot.vercel.app`), cập nhật `CORS_ORIGINS=["https://mascot.vercel.app"]` trên Render.
   - Kiểm tra các luồng chính: Đăng ký → Đăng nhập → Learn / Import → My Vocabulary → Ôn tập → Practice (Multiple Choice + Fill in Blank) → Dashboard.

---

### 2. Danh mục biến môi trường (Environment Variables)

#### Backend (Render Web Service)

| Tên biến | Bắt buộc | Ví dụ / Giá trị gợi ý | Ghi chú |
|---|---|---|---|
| `ENVIRONMENT` | Có | `production` | Khi đặt `production`, `/docs` và `/openapi.json` sẽ tự động tắt |
| `DATABASE_URL` | Có | `postgresql+psycopg://user:pass@ep-xyz.neon.tech/neondb?sslmode=require` | Connection string PostgreSQL (Neon) |
| `CORS_ORIGINS` | Có | `["https://mascot.vercel.app"]` hoặc `https://mascot.vercel.app` | Domain frontend trên Vercel |
| `JWT_SECRET_KEY` | Có | `(chuỗi ngẫu nhiên tối thiểu 32 ký tự)` | Khóa ký token HS256 |
| `JWT_ALGORITHM` | Không | `HS256` | Mặc định `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Không | `30` | Thời hạn JWT (phút) |
| `JWT_ISSUER` | Không | `mascot-api` | Token issuer |
| `JWT_AUDIENCE` | Không | `mascot-frontend` | Token audience |
| `AI_PROVIDER` | Có | `groq` | Provider AI chính |
| `GROQ_API_KEY` | Có | `gsk_...` | API Key từ console.groq.com |
| `GROQ_MODEL` | Không | `openai/gpt-oss-20b` | Model Groq |
| `GROQ_BASE_URL` | Không | `https://api.groq.com/openai/v1` | Endpoint Groq |
| `AI_REQUEST_TIMEOUT_SECONDS` | Không | `20` | Timeout gọi AI (giây) |
| `AI_MAX_OUTPUT_TOKENS` | Không | `800` | Token tối đa cho Vocabulary |
| `AI_EXERCISE_MAX_OUTPUT_TOKENS` | Không | `4000` | Token tối đa cho Exercise |

#### Frontend (Vercel)

| Tên biến | Bắt buộc | Ví dụ / Giá trị gợi ý | Ghi chú |
|---|---|---|---|
| `VITE_API_BASE_URL` | Có | `https://<your-render-service>.onrender.com/api/v1` | URL REST API v1 của Render backend |

---

## Phạm vi hiện tại

Đã có: Phase 1 infrastructure, Phase 2 authentication, Phase 3 Personal Vocabulary CRUD/search/filter/pagination, Phase 3.5 shared Vocabulary Library + Learn/import flow, Phase 4 Vocabulary Review, Phase 5 AI Vocabulary Assistant, Phase 6 deterministic Exercise System, Phase 7 AI Exercise Generator, Phase 8 Dashboard, Phase 9 Full Testing/Security Review và Phase 10 Production Preparation.

Kết quả và các rủi ro còn lại của Phase 9 nằm trong [`REVIEW.md`](./REVIEW.md).

Chưa có: IELTS, TOEIC, Chinese, HSK, RAG hoặc autonomous agents. Basic AI Tutor chỉ là Future/Optional, không nằm trong V1.

