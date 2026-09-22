import {
  Compass,
  Library,
  RefreshCw,
  Dumbbell,
  Flame,
  Sparkles,
  Info,
  ExternalLink,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { PenguinMark } from "../components/PenguinMark";

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

export function AboutPage() {
  return (
    <section className="about-page" aria-labelledby="about-heading">
      <PageHeader
        className="about-header"
        icon={Info}
        eyebrow="GIỚI THIỆU SẢN PHẨM"
        title={<>Học thông minh hơn, <em>từng từ một.</em></>}
        description="Mascot là ứng dụng quản lý và học từ vựng tiếng Anh hiện đại, kết hợp lộ trình chuẩn CEFR, ôn tập ngắt quãng và bài tập sinh bởi AI."
        titleId="about-heading"
      />

      <div className="about-content-layout">
        {/* Section A: Mascot là gì */}
        <section className="about-section about-intro-card" aria-labelledby="what-is-mascot">
          <div className="about-intro-copy">
            <div className="about-section-badge">
              <Sparkles size={16} />
              <span>Về Mascot</span>
            </div>
            <h2 id="what-is-mascot">Mascot là gì?</h2>
            <p>
              <strong>Mascot</strong> là nền tảng học từ vựng tiếng Anh tinh gọn, được thiết kế chuyên biệt
              cho sinh viên và người đi làm. Thay vì học thuộc lòng dàn trải, Mascot giúp bạn tập trung vào
              những từ vựng cốt lõi theo từng trình độ CEFR & HSK, chủ động xây dựng kho từ cá nhân và ghi nhớ bền vững
              thông qua cơ chế ôn tập ngắt quãng có định hướng.
            </p>
            <p>
              Giao diện được thiết kế hiện đại, trang nhã, không gây quá tải thông tin, giúp người học luôn duy trì được
              sự tập trung và hứng khởi mỗi ngày.
            </p>
          </div>
          <div className="about-intro-mascot" aria-hidden="true">
            <div className="about-mascot-stage">
              <span className="hero-sparkle hero-sparkle-one">✦</span>
              <span className="hero-sparkle hero-sparkle-two">✦</span>
              <PenguinMark size={140} variant="scholar" />
            </div>
          </div>
        </section>

        {/* Section B: Mascot có gì */}
        <section className="about-section" aria-labelledby="features-heading">
          <div className="section-heading-row">
            <div>
              <p className="eyebrow">TÍNH NĂNG NỔI BẬT</p>
              <h2 id="features-heading">Mascot có gì?</h2>
            </div>
          </div>

          <div className="about-features-grid">
            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-cefr">
                <Compass size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Thư viện chuẩn CEFR</h3>
                <p>Lộ trình từ vựng phong phú từ A1 đến C2, sắp xếp khoa học theo các chủ đề thiết thực trong đời sống và công việc.</p>
              </div>
            </article>

            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-personal">
                <Library size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Từ vựng của tôi</h3>
                <p>Kho từ vựng cá nhân hoá hoàn toàn. Tự do thêm từ mới, phân loại theo chủ đề và quản lý nghĩa chuẩn xác.</p>
              </div>
            </article>

            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-review">
                <RefreshCw size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Ôn tập thông minh</h3>
                <p>Cơ chế thẻ ghi nhớ (flashcard) tự đánh giá với thuật toán giãn cách thời gian để chuyển từ mới thành thành thạo.</p>
              </div>
            </article>

            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-practice">
                <Dumbbell size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Luyện tập cùng AI</h3>
                <p>Tự động tạo bài tập trắc nghiệm ngữ cảnh và bài điền đoạn văn từ chính kho từ vựng bạn đang học.</p>
              </div>
            </article>

            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-streak">
                <Flame size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Tiến độ & Streak</h3>
                <p>Theo dõi chuỗi ngày học liên tục, tỷ lệ làm bài chính xác và bảng thống kê từ vựng trực quan, thực tế.</p>
              </div>
            </article>

            <article className="about-feature-card">
              <div className="feature-card-icon feature-icon-ai">
                <Sparkles size={22} />
              </div>
              <div className="feature-card-body">
                <h3>Trợ lý từ vựng AI</h3>
                <p>Nhập một từ bất kỳ để nhận bản nháp gợi ý định nghĩa, nghĩa tiếng Việt, ước tính CEFR và câu ví dụ chuẩn mực.</p>
              </div>
            </article>
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
              <div className="author-avatar">
                <span>DQ</span>
              </div>
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
