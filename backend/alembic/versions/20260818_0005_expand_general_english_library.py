"""Expand the curated General English vocabulary library.

Revision ID: 20260818_0005
Revises: 20260815_0004
Create Date: 2026-08-18 00:00:00
"""

import unicodedata
import uuid
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260818_0005"
down_revision: str | Sequence[str] | None = "20260815_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEED_NAMESPACE = uuid.UUID("7a313c6f-9a8e-4b51-bb7c-ec55b1496c70")
GENERAL_ENGLISH_TRACK_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")

# This is deliberately a compact, curated starter library—not an official CEFR dictionary.
# Every tuple is: word, part of speech, simple English definition, Vietnamese translation,
# one natural English example sentence.
CATALOG_EXPANSION = [
    ("a1-daily-life", "A1", "Daily Life", [
        ("tidy", "verb", "To make a place clean and neat.", "dọn dẹp gọn gàng", "I tidy my desk before dinner."),
        ("errand", "noun", "A short trip to do a small task.", "việc vặt", "I need to run an errand after class."),
        ("laundry", "noun", "Clothes that need to be washed.", "quần áo cần giặt", "The laundry is in the basket."),
        ("prepare", "verb", "To get something ready.", "chuẩn bị", "We prepare dinner together every evening."),
        ("usually", "adverb", "In the way that happens most often.", "thường thường", "I usually walk to school."),
    ]),
    ("a1-family", "A1", "Family", [
        ("grandparent", "noun", "The parent of your mother or father.", "ông hoặc bà", "My grandparents tell wonderful stories."),
        ("relative", "noun", "A person in your family.", "người thân", "We visit our relatives at Tet."),
        ("uncle", "noun", "The brother of your mother or father.", "chú, bác hoặc cậu", "My uncle works in Hanoi."),
        ("aunt", "noun", "The sister of your mother or father.", "cô, dì hoặc bác gái", "My aunt makes a great cake."),
        ("care", "verb", "To look after someone or something.", "chăm sóc", "He cares for his little sister."),
    ]),
    ("a1-school", "A1", "School", [
        ("classroom", "noun", "A room where students have lessons.", "lớp học", "Our classroom has large windows."),
        ("subject", "noun", "An area of study at school.", "môn học", "English is my favourite subject."),
        ("homework", "noun", "Work students do after school.", "bài tập về nhà", "I finish my homework before playing games."),
        ("lesson", "noun", "A period of learning or teaching.", "bài học", "Today's lesson is about animals."),
        ("answer", "verb", "To say or write something in reply.", "trả lời", "Please answer the first question."),
        ("borrow", "verb", "To take something and return it later.", "mượn", "Can I borrow your ruler?"),
        ("dictionary", "noun", "A book or tool that explains words.", "từ điển", "She checks the word in a dictionary."),
        ("practice", "verb", "To do something repeatedly to improve.", "luyện tập", "We practice speaking English every day."),
        ("project", "noun", "A piece of work done over a period of time.", "dự án", "Our science project is due on Friday."),
        ("uniform", "noun", "Special clothes worn by students at school.", "đồng phục", "Students wear a blue uniform on Monday."),
    ]),
    ("a1-food", "A1", "Food", [
        ("ingredient", "noun", "One of the foods used to make a dish.", "nguyên liệu", "Rice is an important ingredient in this meal."),
        ("recipe", "noun", "Instructions for cooking a dish.", "công thức nấu ăn", "This recipe is easy to follow."),
        ("hungry", "adjective", "Wanting to eat food.", "đói", "I am hungry after football practice."),
        ("delicious", "adjective", "Having a very good taste.", "ngon", "The soup smells delicious."),
        ("fresh", "adjective", "Recently made, picked, or prepared.", "tươi", "We buy fresh vegetables at the market."),
        ("order", "verb", "To ask for food or drink in a restaurant.", "gọi món", "They order noodles for lunch."),
        ("portion", "noun", "An amount of food for one person.", "khẩu phần", "This portion is big enough for two people."),
        ("spicy", "adjective", "Having a strong hot taste.", "cay", "My brother likes spicy food."),
        ("taste", "verb", "To have a particular flavour.", "có vị", "The tea tastes sweet."),
        ("meal", "noun", "An occasion when people eat food.", "bữa ăn", "Breakfast is my favourite meal."),
    ]),
    ("a2-travel", "A2", "Travel", [
        ("passport", "noun", "An official document used for international travel.", "hộ chiếu", "Keep your passport in a safe place."),
        ("departure", "noun", "The act of leaving a place.", "sự khởi hành", "Our departure is at six in the morning."),
        ("arrival", "noun", "The act of reaching a place.", "sự đến nơi", "Please wait in the hall for my arrival."),
        ("tourist", "noun", "A person who visits a place for pleasure.", "khách du lịch", "Many tourists visit Hoi An in summer."),
        ("ticket", "noun", "A piece of paper or digital record that allows travel.", "vé", "I bought a train ticket online."),
    ]),
    ("a2-work", "A2", "Work", [
        ("interview", "noun", "A meeting to decide if someone is right for a job.", "buổi phỏng vấn", "Her job interview is tomorrow morning."),
        ("manager", "noun", "A person who controls part of a company or team.", "quản lý", "The manager leads our weekly meeting."),
        ("salary", "noun", "Money paid regularly for work.", "lương", "His salary arrives at the end of the month."),
        ("meeting", "noun", "An event where people discuss work.", "cuộc họp", "We have a meeting at ten o'clock."),
        ("training", "noun", "Learning skills for a job or activity.", "đào tạo", "New staff receive training in their first week."),
    ]),
    ("a2-shopping", "A2", "Shopping", [
        ("customer", "noun", "A person who buys goods or services.", "khách hàng", "The customer asked for a smaller size."),
        ("discount", "noun", "A lower price than usual.", "giảm giá", "This shop gives students a discount."),
        ("receipt", "noun", "A paper that shows what you bought.", "hóa đơn", "Please keep the receipt for your records."),
        ("cashier", "noun", "A person who receives payment in a shop.", "thu ngân", "The cashier gave me my change."),
        ("exchange", "verb", "To give something back and get another item.", "đổi hàng", "Can I exchange this shirt for a larger one?"),
        ("afford", "verb", "To have enough money to pay for something.", "có đủ khả năng chi trả", "I cannot afford that phone right now."),
        ("bargain", "noun", "Something sold at a lower price than expected.", "món hời", "These shoes were a real bargain."),
        ("brand", "noun", "The name of a product made by a company.", "thương hiệu", "This brand makes comfortable backpacks."),
        ("queue", "noun", "A line of people waiting for something.", "hàng người xếp hàng", "We waited in a queue at the checkout."),
        ("refund", "noun", "Money returned after you give something back.", "hoàn tiền", "The store gave me a full refund."),
    ]),
    ("a2-health", "A2", "Health", [
        ("appointment", "noun", "An arranged time to meet someone.", "lịch hẹn", "I have a doctor's appointment at three."),
        ("exercise", "noun", "Physical activity that keeps you healthy.", "bài tập thể dục", "Regular exercise helps me sleep well."),
        ("healthy", "adjective", "In good physical condition.", "khỏe mạnh", "A healthy breakfast gives you energy."),
        ("medicine", "noun", "A substance used to treat illness.", "thuốc", "Take this medicine after meals."),
        ("symptom", "noun", "A sign that shows someone may be ill.", "triệu chứng", "A cough can be a symptom of a cold."),
        ("rest", "verb", "To relax after activity or illness.", "nghỉ ngơi", "You should rest when you feel tired."),
        ("injury", "noun", "Damage to part of the body.", "chấn thương", "He missed the match because of a leg injury."),
        ("diet", "noun", "The food a person usually eats.", "chế độ ăn", "A balanced diet is important for health."),
        ("recover", "verb", "To become healthy again after illness.", "hồi phục", "She recovered quickly from the flu."),
        ("stress", "noun", "Worry caused by difficult situations.", "căng thẳng", "A short walk can reduce stress."),
    ]),
    ("b1-education", "B1", "Education", [
        ("graduate", "verb", "To complete a course of study and receive a degree.", "tốt nghiệp", "She will graduate from university next year."),
        ("research", "noun", "Careful study to discover information.", "nghiên cứu", "Our group is doing research on clean energy."),
        ("scholarship", "noun", "Money given to help someone study.", "học bổng", "He received a scholarship for excellent results."),
        ("academic", "adjective", "Related to study or education.", "thuộc học thuật", "The library supports academic work."),
        ("concentrate", "verb", "To give full attention to something.", "tập trung", "It is hard to concentrate in a noisy room."),
    ]),
    ("b1-communication", "B1", "Communication", [
        ("announce", "verb", "To tell people something officially.", "thông báo", "The school announced the new timetable."),
        ("audience", "noun", "The people who watch or listen to something.", "khán giả", "The audience listened carefully to her speech."),
        ("express", "verb", "To show or communicate a thought or feeling.", "bày tỏ", "He expressed his opinion politely."),
        ("misunderstand", "verb", "To understand something incorrectly.", "hiểu lầm", "I misunderstood the instructions."),
        ("respond", "verb", "To say or do something as an answer.", "phản hồi", "Please respond to the email today."),
    ]),
    ("b1-environment", "B1", "Environment", [
        ("recycle", "verb", "To use materials again instead of throwing them away.", "tái chế", "We recycle paper and plastic at school."),
        ("pollution", "noun", "Harmful substances in air, water, or land.", "ô nhiễm", "Air pollution is worse in large cities."),
        ("renewable", "adjective", "Able to be naturally replaced.", "có thể tái tạo", "Solar power is a renewable energy source."),
        ("conserve", "verb", "To protect something from being wasted.", "bảo tồn, tiết kiệm", "We should conserve water at home."),
        ("climate", "noun", "The usual weather conditions in a place.", "khí hậu", "The climate here is warm and wet."),
        ("waste", "noun", "Unwanted material that is thrown away.", "rác thải", "Food waste fills many rubbish bins."),
        ("protect", "verb", "To keep someone or something safe.", "bảo vệ", "Trees protect the soil from heavy rain."),
        ("species", "noun", "A group of similar living things.", "loài", "This forest is home to many bird species."),
        ("reduce", "verb", "To make something smaller or less.", "giảm", "We can reduce plastic use every day."),
        ("resource", "noun", "A useful material or supply.", "tài nguyên", "Clean water is a valuable resource."),
    ]),
    ("b1-technology", "B1", "Technology", [
        ("device", "noun", "A piece of equipment made for a purpose.", "thiết bị", "This device tracks your daily steps."),
        ("download", "verb", "To copy data from the internet to a device.", "tải xuống", "Download the file before the meeting."),
        ("online", "adjective", "Connected to or available on the internet.", "trực tuyến", "The course has an online discussion group."),
        ("screen", "noun", "The flat surface that shows images on a device.", "màn hình", "My screen is too bright at night."),
        ("update", "verb", "To make something more modern or correct.", "cập nhật", "Please update the app this evening."),
        ("digital", "adjective", "Using electronic technology or information.", "kỹ thuật số", "The museum has a digital guide."),
        ("password", "noun", "A secret word used to access an account.", "mật khẩu", "Never share your password with anyone."),
        ("connect", "verb", "To join something to a network or system.", "kết nối", "Connect your laptop to the projector."),
        ("website", "noun", "A group of related pages on the internet.", "trang web", "The website explains how to apply."),
        ("software", "noun", "Programs that run on a computer.", "phần mềm", "The new software makes the task easier."),
    ]),
    ("b2-work-business", "B2", "Work & Business", [
        ("strategy", "noun", "A careful plan for achieving a goal.", "chiến lược", "The team developed a new sales strategy."),
        ("budget", "noun", "A plan for spending money.", "ngân sách", "We need to stay within our budget."),
        ("launch", "verb", "To introduce a new product or service.", "ra mắt", "The company will launch the product in May."),
        ("profit", "noun", "Money left after costs are paid.", "lợi nhuận", "The business made a small profit this year."),
        ("compromise", "noun", "An agreement where each side accepts less than it wanted.", "sự thỏa hiệp", "Both sides reached a compromise."),
    ]),
    ("b2-technology", "B2", "Technology", [
        ("algorithm", "noun", "A set of rules used to solve a problem.", "thuật toán", "The app uses an algorithm to suggest videos."),
        ("database", "noun", "An organized collection of information.", "cơ sở dữ liệu", "Customer details are stored in a secure database."),
        ("interface", "noun", "The part of a system that a user interacts with.", "giao diện", "The new interface is simple to use."),
        ("network", "noun", "A group of connected computers or people.", "mạng lưới", "The office network is being repaired."),
        ("upgrade", "verb", "To improve a system or product to a newer version.", "nâng cấp", "We need to upgrade the server this month."),
    ]),
    ("b2-media", "B2", "Media", [
        ("headline", "noun", "The title of a news story.", "tiêu đề tin tức", "The headline caught my attention."),
        ("journalist", "noun", "A person who writes news reports.", "nhà báo", "The journalist interviewed the mayor."),
        ("broadcast", "verb", "To send a programme by television or radio.", "phát sóng", "The station will broadcast the match live."),
        ("editor", "noun", "A person who prepares writing for publication.", "biên tập viên", "The editor checked the article carefully."),
        ("source", "noun", "A person or place that provides information.", "nguồn tin", "Always check the source of a news story."),
        ("report", "verb", "To give information about an event.", "tường thuật", "Several newspapers reported the story."),
        ("publish", "verb", "To prepare writing for people to read.", "xuất bản", "The magazine will publish her interview."),
        ("accurate", "adjective", "Correct and free from mistakes.", "chính xác", "The report must be accurate."),
        ("audience", "noun", "The people who watch, read, or listen to media.", "khán giả", "The show has a young audience."),
        ("influence", "noun", "The power to affect people or events.", "ảnh hưởng", "Social media has a strong influence on trends."),
    ]),
    ("b2-culture", "B2", "Culture", [
        ("tradition", "noun", "A custom passed from one generation to another.", "truyền thống", "Making bánh chưng is a family tradition."),
        ("heritage", "noun", "Buildings, art, and traditions from the past.", "di sản", "The city protects its cultural heritage."),
        ("festival", "noun", "A special event that celebrates something.", "lễ hội", "The lantern festival attracts many visitors."),
        ("diverse", "adjective", "Including many different types of people or things.", "đa dạng", "The class has a diverse group of students."),
        ("custom", "noun", "A traditional way of behaving.", "phong tục", "Removing shoes is a local custom."),
        ("identity", "noun", "The qualities that make a person or group different.", "bản sắc", "Language is part of cultural identity."),
        ("ceremony", "noun", "A formal event for a special occasion.", "nghi lễ", "The opening ceremony began at noon."),
        ("preserve", "verb", "To keep something in its original state.", "gìn giữ", "The museum helps preserve old documents."),
        ("community", "noun", "People living in the same area or sharing an interest.", "cộng đồng", "The event brought the community together."),
        ("appreciate", "verb", "To understand the value of something.", "trân trọng", "Visitors appreciate the local art."),
    ]),
    ("c1-leadership", "C1", "Leadership", [
        ("delegate", "verb", "To give a task or responsibility to another person.", "ủy quyền", "A good leader knows when to delegate tasks."),
        ("accountability", "noun", "Responsibility for actions and decisions.", "trách nhiệm giải trình", "The policy improves accountability across the team."),
        ("vision", "noun", "A clear idea of what the future should be like.", "tầm nhìn", "Her vision inspired the whole organization."),
        ("mentor", "noun", "An experienced person who gives guidance.", "người cố vấn", "My mentor helped me prepare for the interview."),
        ("initiative", "noun", "The ability to act without being told.", "tính chủ động", "He showed initiative by solving the issue early."),
        ("empower", "verb", "To give someone confidence or authority to act.", "trao quyền", "Managers should empower staff to make decisions."),
        ("resilient", "adjective", "Able to recover quickly from difficulties.", "kiên cường", "The team remained resilient after the setback."),
        ("consensus", "noun", "General agreement among a group.", "sự đồng thuận", "The committee reached a consensus."),
        ("integrity", "noun", "The quality of being honest and principled.", "sự chính trực", "Integrity is essential in leadership."),
        ("motivate", "verb", "To make someone want to do something well.", "tạo động lực", "Clear goals motivate people to improve."),
    ]),
    ("c1-global-issues", "C1", "Global Issues", [
        ("inequality", "noun", "An unfair difference in wealth or opportunity.", "bất bình đẳng", "Income inequality affects many communities."),
        ("humanitarian", "adjective", "Related to helping people in need.", "nhân đạo", "The agency delivered humanitarian aid."),
        ("displacement", "noun", "The forced movement of people from their homes.", "sự di dời", "Conflict caused widespread displacement."),
        ("sustainable", "adjective", "Able to continue without causing serious harm.", "bền vững", "The city needs sustainable transport."),
        ("crisis", "noun", "A time of great danger or difficulty.", "khủng hoảng", "Leaders met to discuss the energy crisis."),
        ("cooperation", "noun", "Working together to achieve something.", "sự hợp tác", "International cooperation is necessary."),
        ("vulnerable", "adjective", "Likely to be harmed or affected easily.", "dễ bị tổn thương", "Children are vulnerable during disasters."),
        ("intervention", "noun", "Action taken to improve a situation.", "sự can thiệp", "Early intervention can save lives."),
        ("poverty", "noun", "The state of being very poor.", "nghèo đói", "Education can help reduce poverty."),
        ("diplomatic", "adjective", "Related to relations between countries.", "ngoại giao", "They found a diplomatic solution."),
    ]),
    ("c1-psychology", "C1", "Psychology", [
        ("perception", "noun", "The way someone understands or notices something.", "nhận thức", "Our perception of risk can change over time."),
        ("behaviour", "noun", "The way a person acts.", "hành vi", "Sleep can affect human behaviour."),
        ("cognitive", "adjective", "Related to thinking, learning, or remembering.", "thuộc nhận thức", "The game develops cognitive skills."),
        ("anxiety", "noun", "A feeling of worry or nervousness.", "lo âu", "Public speaking can cause anxiety."),
        ("motivation", "noun", "A reason for doing something.", "động lực", "Her motivation comes from helping others."),
        ("bias", "noun", "An unfair preference for one thing or person.", "thiên kiến", "We should be aware of personal bias."),
        ("empathy", "noun", "The ability to understand another person's feelings.", "sự đồng cảm", "Empathy improves communication."),
        ("habit", "noun", "Something a person does regularly.", "thói quen", "Reading before bed is a useful habit."),
        ("cope", "verb", "To deal successfully with a difficult situation.", "đối phó", "She learned to cope with pressure."),
        ("confidence", "noun", "Belief in your own ability.", "sự tự tin", "Practice builds confidence over time."),
    ]),
    ("c1-innovation", "C1", "Innovation", [
        ("breakthrough", "noun", "An important new discovery or development.", "bước đột phá", "The research led to a medical breakthrough."),
        ("prototype", "noun", "The first model of a new product.", "mẫu thử", "The team tested a prototype of the device."),
        ("entrepreneur", "noun", "A person who starts and runs a business.", "doanh nhân khởi nghiệp", "The entrepreneur built a successful app."),
        ("disrupt", "verb", "To change an industry or process strongly.", "làm thay đổi mạnh", "New technology can disrupt old markets."),
        ("feasible", "adjective", "Possible and practical to do.", "khả thi", "The plan is feasible with enough funding."),
        ("adapt", "verb", "To change in order to deal with a new situation.", "thích nghi", "Small companies must adapt quickly."),
        ("collaborate", "verb", "To work together with others.", "hợp tác", "The designers collaborate with engineers."),
        ("solution", "noun", "An answer to a problem.", "giải pháp", "They found a creative solution."),
        ("experiment", "verb", "To try a new idea to see what happens.", "thử nghiệm", "The lab experiments with new materials."),
        ("transform", "verb", "To change completely in form or character.", "chuyển đổi", "Digital tools transform how we work."),
    ]),
    ("c2-philosophy", "C2", "Philosophy", [
        ("consciousness", "noun", "Awareness of yourself and the world around you.", "ý thức", "The lecture explored human consciousness."),
        ("rational", "adjective", "Based on clear reason rather than emotion.", "hợp lý", "We need a rational argument."),
        ("paradox", "noun", "A statement that seems impossible but may be true.", "nghịch lý", "The idea creates an interesting paradox."),
        ("existence", "noun", "The state of being real or alive.", "sự tồn tại", "The novel questions the meaning of existence."),
        ("perceive", "verb", "To become aware of something through the senses or mind.", "nhận thức", "People perceive the same event differently."),
        ("virtue", "noun", "A good moral quality.", "đức tính", "Patience is often seen as a virtue."),
        ("reasoning", "noun", "The process of thinking logically.", "lập luận", "Her reasoning was clear and convincing."),
        ("assumption", "noun", "Something accepted as true without proof.", "giả định", "The argument rests on a weak assumption."),
        ("notion", "noun", "An idea or belief about something.", "khái niệm", "He rejected the notion of fixed talent."),
        ("interpret", "verb", "To explain the meaning of something.", "diễn giải", "Different readers interpret the poem differently."),
    ]),
    ("c2-ethics", "C2", "Ethics", [
        ("dilemma", "noun", "A difficult choice between two bad options.", "tình thế tiến thoái lưỡng nan", "The case presents an ethical dilemma."),
        ("principle", "noun", "A basic rule or belief that guides behaviour.", "nguyên tắc", "Fairness is an important principle."),
        ("justify", "verb", "To show that something is reasonable or right.", "biện minh", "Can the decision be justified?"),
        ("moral", "adjective", "Related to ideas of right and wrong.", "thuộc đạo đức", "The story raises a moral question."),
        ("obligation", "noun", "A duty that you must do.", "nghĩa vụ", "We have an obligation to protect others."),
        ("consequence", "noun", "A result of an action or decision.", "hệ quả", "Every choice has a consequence."),
        ("ethical", "adjective", "Related to accepted ideas about right and wrong.", "đạo đức", "The company follows ethical standards."),
        ("accountable", "adjective", "Responsible for your actions.", "chịu trách nhiệm", "Leaders must be accountable to the public."),
        ("consent", "noun", "Permission for something to happen.", "sự đồng ý", "The study requires informed consent."),
        ("impartial", "adjective", "Not supporting one side more than another.", "khách quan", "An impartial judge heard the case."),
    ]),
    ("c2-public-policy", "C2", "Public Policy", [
        ("legislation", "noun", "Laws considered or made by a government.", "pháp luật", "New legislation protects consumer data."),
        ("regulation", "noun", "An official rule that controls an activity.", "quy định", "The regulation limits factory emissions."),
        ("implement", "verb", "To put a plan or policy into action.", "triển khai", "The city will implement the policy next year."),
        ("infrastructure", "noun", "Basic systems such as roads and power supplies.", "cơ sở hạ tầng", "Public transport infrastructure needs investment."),
        ("subsidy", "noun", "Money given by a government to support an activity.", "trợ cấp", "Farmers receive a subsidy for clean energy."),
        ("stakeholder", "noun", "A person or group affected by a decision.", "bên liên quan", "Officials consulted every stakeholder."),
        ("allocate", "verb", "To give something to a particular purpose.", "phân bổ", "The council allocated funds to schools."),
        ("governance", "noun", "The way an organization or country is controlled.", "quản trị", "Good governance builds public trust."),
        ("mandate", "noun", "An official order or authority to act.", "ủy nhiệm chính thức", "The agency has a mandate to inspect sites."),
        ("evaluate", "verb", "To judge the quality or value of something.", "đánh giá", "Researchers evaluate the policy's effects."),
    ]),
    ("c2-global-economics", "C2", "Global Economics", [
        ("inflation", "noun", "A general rise in prices over time.", "lạm phát", "Inflation has increased food prices."),
        ("recession", "noun", "A period when the economy becomes weaker.", "suy thoái kinh tế", "The country recovered slowly from the recession."),
        ("tariff", "noun", "A tax on goods brought into a country.", "thuế quan", "The tariff made imported goods more expensive."),
        ("currency", "noun", "The money used in a country.", "tiền tệ", "The local currency changed in value."),
        ("investment", "noun", "Money used to develop a business or project.", "đầu tư", "Foreign investment created new jobs."),
        ("supply", "noun", "The amount of something available.", "nguồn cung", "A shortage reduced the supply of oil."),
        ("demand", "noun", "The desire or need to buy something.", "nhu cầu", "Demand for online learning is growing."),
        ("trade", "noun", "The buying and selling of goods between people or countries.", "thương mại", "The agreement supports international trade."),
        ("inequality", "noun", "An unfair difference in wealth or opportunity.", "bất bình đẳng", "Economic inequality remains a concern."),
        ("productivity", "noun", "The rate at which work or goods are produced.", "năng suất", "Better tools can improve productivity."),
    ]),
]


def _seed_id(kind: str, value: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"{kind}:{value}")


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value.strip()).casefold()


def upgrade() -> None:
    vocabulary_sets = sa.table(
        "vocabulary_sets",
        sa.column("id", sa.Uuid()),
        sa.column("learning_track_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("level_code", sa.String()),
        sa.column("topic", sa.String()),
        sa.column("order_index", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    vocabulary_entries = sa.table(
        "vocabulary_entries",
        sa.column("id", sa.Uuid()),
        sa.column("vocabulary_set_id", sa.Uuid()),
        sa.column("word", sa.String()),
        sa.column("normalized_word", sa.String()),
        sa.column("part_of_speech", sa.String()),
        sa.column("meaning", sa.Text()),
        sa.column("translation", sa.Text()),
        sa.column("translation_language_code", sa.String()),
        sa.column("example_sentences", postgresql.JSONB()),
        sa.column("order_index", sa.Integer()),
    )
    bind = op.get_bind()

    for set_index, (code, level, name, entries) in enumerate(CATALOG_EXPANSION):
        set_id = _seed_id("set", code)
        bind.execute(
            postgresql.insert(vocabulary_sets)
            .values(
                id=set_id,
                learning_track_id=GENERAL_ENGLISH_TRACK_ID,
                name=name,
                description=f"Curated {level} vocabulary set for General English learners.",
                level_code=level,
                topic=name,
                order_index=set_index,
                is_active=True,
            )
            .on_conflict_do_nothing(constraint="uq_vocab_sets_track_level_topic")
        )

        for entry_index, (word, part_of_speech, meaning, translation, example) in enumerate(entries):
            entry_id = _seed_id("entry", f"{code}:{word}:{part_of_speech}")
            exists = bind.scalar(
                sa.select(vocabulary_entries.c.id).where(vocabulary_entries.c.id == entry_id)
            )
            if exists is not None:
                continue
            bind.execute(
                vocabulary_entries.insert().values(
                    id=entry_id,
                    vocabulary_set_id=set_id,
                    word=word,
                    normalized_word=_normalize(word),
                    part_of_speech=part_of_speech,
                    meaning=meaning,
                    translation=translation,
                    translation_language_code="vi",
                    example_sentences=[example],
                    order_index=entry_index + (5 if code in {
                        "a1-daily-life", "a1-family", "a2-travel", "a2-work",
                        "b1-education", "b1-communication", "b2-work-business", "b2-technology",
                    } else 0),
                )
            )


def downgrade() -> None:
    # This is intentionally a non-destructive content migration. Removing catalog rows could
    # erase source metadata from vocabulary that learners have already imported.
    pass
