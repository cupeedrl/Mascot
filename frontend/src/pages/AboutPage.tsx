import { useState } from "react";
import {
  BookmarkPlus,
  Bot,
  CalendarDays,
  Compass,
  Dumbbell,
  Info,
  Languages,
  Library,
  RefreshCw,
  Search,
  Sparkles,
} from "lucide-react";
import { MascotTip, PageDoodles } from "../components/PageDoodles";
import { PageHeader } from "../components/PageHeader";
import { PenguinMark } from "../components/PenguinMark";

const FEATURES = [
  {
    icon: Compass,
    tone: "cefr",
    title: "Tiếng Anh theo CEFR",
    body: "Thư viện từ A1 đến C2, chia theo chủ đề gần gũi như gia đình, trường học, công việc. Mỗi từ có phiên âm IPA, nghĩa tiếng Việt và câu ví dụ.",
  },
  {
    icon: Languages,
    tone: "hsk",
    title: "Tiếng Trung theo HSK 3.0",
    body: "10.999 từ từ HSK 1 đến HSK 7–9, xếp vào 652 chủ đề và chia thành từng phần tối đa 50 từ. Có pinyin, từ loại và nghĩa tiếng Việt.",
  },
  {
    icon: Library,
    tone: "personal",
    title: "Từ vựng của tôi",
    body: "Sổ từ của riêng bạn: lưu từ trong thư viện chỉ với một lần bấm, tự thêm từ mới, gắn chủ đề, lọc theo trạng thái và trình độ.",
  },
  {
    icon: RefreshCw,
    tone: "review",
    title: "Ôn tập ngắt quãng",
    body: "Thẻ ghi nhớ lật mặt. Bạn tự chấm mức nhớ, Mascot hẹn ngày ôn tiếp theo để từ mới dần thành từ thành thạo.",
  },
  {
    icon: Dumbbell,
    tone: "practice",
    title: "Luyện tập cùng AI",
    body: "AI soạn câu hỏi trắc nghiệm và điền từ từ chính sổ từ của bạn. Đáp án luôn được chấm theo quy tắc cố định, kèm giải thích tiếng Việt.",
  },
  {
    icon: Bot,
    tone: "ai",
    title: "Trợ lý Mascot AI",
    body: "Hỏi nghĩa, cách dùng hay xin gợi ý học ngay trong ứng dụng. Mascot chỉ thêm từ vào sổ khi bạn bấm xác nhận.",
  },
  {
    icon: CalendarDays,
    tone: "streak",
    title: "Lịch học và chuỗi ngày",
    body: "Lịch hoạt động theo tháng, chuỗi ngày học liên tiếp, gợi ý việc nên làm mỗi ngày và một “Từ của hôm nay” đúng trình độ.",
  },
] as const;

const STEPS = [
  { icon: Search, title: "Chọn chủ đề", body: "Chọn ngôn ngữ, trình độ và một chủ đề bạn thích." },
  { icon: BookmarkPlus, title: "Lưu từ", body: "Lưu vài từ vào sổ, 5–10 từ mỗi ngày là vừa sức." },
  { icon: Sparkles, title: "Ôn và luyện", body: "Ôn đúng lúc Mascot nhắc, luyện tập để nhớ chắc." },
] as const;

function GitHubIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
      <path d="M9 18c-4.51 2-5-2-7-2" />
    </svg>
  );
}

function LinkedInIcon({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
      <rect width="4" height="12" x="2" y="9" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

/** Author photo (public/images/author.jpg); falls back to initials if missing. */
function AuthorAvatar() {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="author-avatar">
        <span>DQ</span>
      </div>
    );
  }
  return (
    <img
      className="author-photo"
      src="/images/author.jpg"
      alt="Ảnh chân dung Dat Chu Quoc"
      width={96}
      height={96}
      onError={() => setFailed(true)}
    />
  );
}

export function AboutPage() {
  return (
    <section className="about-page" aria-labelledby="about-heading">
      <PageHeader
        className="about-header"
        icon={Info}
        eyebrow="GIỚI THIỆU MASCOT"
        title={<>Học thông minh hơn, <em>từng từ một.</em></>}
        description="Mascot là ứng dụng học từ vựng tiếng Anh theo CEFR và tiếng Trung theo HSK 3.0: lưu từ theo chủ đề, ôn đúng lúc và luyện tập cùng AI."
        titleId="about-heading"
        decoration={<PageDoodles variant="about" />}
        tip={<MascotTip tone="about">Mình là chim cánh cụt Mascot, rất vui được học cùng bạn mỗi ngày!</MascotTip>}
      />

      <div className="about-content-layout">
        <section className="about-section about-intro-card" aria-labelledby="what-is-mascot">
          <div className="about-intro-copy">
            <div className="about-section-badge">
              <Sparkles size={16} />
              <span>Về Mascot</span>
            </div>
            <h2 id="what-is-mascot">Mascot là gì?</h2>
            <p>
              <strong>Mascot</strong> là người bạn học từ vựng dành cho sinh viên và người đi làm. Thay vì học
              thuộc lòng dàn trải, bạn học theo từng trình độ CEFR hoặc HSK, lưu những từ mình cần vào sổ từ cá
              nhân và ôn lại đúng lúc sắp quên.
            </p>
            <p>
              Chú chim cánh cụt đội mũ tốt nghiệp sẽ gợi ý việc nên làm mỗi ngày, nhắc bạn giữ chuỗi ngày học và
              luôn sẵn sàng trả lời khi bạn hỏi. Giao diện gọn gàng để bạn tập trung vào điều quan trọng nhất:
              nhớ được từ.
            </p>
            <ul className="about-facts" aria-label="Mascot trong vài con số">
              <li><b>2</b><span>ngôn ngữ</span></li>
              <li><b>6</b><span>cấp CEFR</span></li>
              <li><b>10.999</b><span>từ HSK</span></li>
              <li><b>652</b><span>chủ đề HSK</span></li>
            </ul>
          </div>
          <div className="about-intro-mascot" aria-hidden="true">
            <div className="about-mascot-stage">
              <span className="hero-sparkle hero-sparkle-one">✦</span>
              <span className="hero-sparkle hero-sparkle-two">✦</span>
              <span className="about-mascot-bubble">你好! Hello!</span>
              <PenguinMark size={140} variant="scholar" />
            </div>
          </div>
        </section>

        <section className="about-section" aria-labelledby="how-heading">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">CÁCH HỌC CÙNG MASCOT</p>
              <h2 id="how-heading">Ba bước mỗi ngày</h2>
            </div>
          </div>
          <ol className="about-steps">
            {STEPS.map((step, index) => (
              <li key={step.title}>
                <span className="about-step-number">{index + 1}</span>
                <span className="about-step-icon"><step.icon size={20} aria-hidden="true" /></span>
                <strong>{step.title}</strong>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="about-section" aria-labelledby="features-heading">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">TÍNH NĂNG NỔI BẬT</p>
              <h2 id="features-heading">Mascot có gì?</h2>
            </div>
          </div>

          <div className="about-features-grid">
            {FEATURES.map((feature) => (
              <article className="about-feature-card" key={feature.title}>
                <div className={`feature-card-icon feature-icon-${feature.tone}`}>
                  <feature.icon size={22} />
                </div>
                <div className="feature-card-body">
                  <h3>{feature.title}</h3>
                  <p>{feature.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Section C: Người xây dựng */}
        <section className="about-section about-author-section" aria-labelledby="author-heading">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">TÁC GIẢ</p>
              <h2 id="author-heading">Người xây dựng</h2>
            </div>
          </div>

          <div className="about-author-card">
            <div className="author-avatar-wrap">
              <AuthorAvatar />
            </div>
            <div className="author-details">
              <div className="author-title-group">
                <h3>Dat Chu Quoc</h3>
                <span className="author-role">Developer of Mascot</span>
              </div>
              <p className="author-bio">
                Xây dựng Mascot với định hướng tạo nên một sản phẩm học ngoại ngữ tinh gọn, chuẩn mực và thông minh.
                Tập trung tối đa vào trải nghiệm người dùng, tính chính xác và hiệu quả học tập thực tế.
              </p>
              <div className="author-links">
                <a
                  className="author-link-btn"
                  href="https://github.com/cupeedrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="GitHub của Dat Chu Quoc"
                >
                  <GitHubIcon size={18} />
                  <span>GitHub</span>
                </a>
                <a
                  className="author-link-btn"
                  href="https://www.linkedin.com/in/dat-chu-quoc-583599387/"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="LinkedIn của Dat Chu Quoc"
                >
                  <LinkedInIcon size={18} />
                  <span>LinkedIn</span>
                </a>
              </div>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}
