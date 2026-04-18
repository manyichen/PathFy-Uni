-- 创建性格测试题目表
CREATE TABLE IF NOT EXISTS personality_test_questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    dimension VARCHAR(20) NOT NULL,
    option_a_type VARCHAR(1) NOT NULL,
    option_b_type VARCHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建性格测试答案表
CREATE TABLE IF NOT EXISTS personality_test_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    question_id INT NOT NULL,
    user_choice VARCHAR(1) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES personality_test_questions(id)
);

-- 创建人物画像表
CREATE TABLE IF NOT EXISTS personality_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    mbti_type VARCHAR(4) NOT NULL,
    personality_analysis TEXT NOT NULL,
    recommended_jobs TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入MBTI性格测试题目（50题）
INSERT INTO personality_test_questions (question_text, option_a, option_b, dimension, option_a_type, option_b_type) VALUES
-- 外向性（E） vs 内向性（I）
('我更倾向从以下何处获得力量', '朋友和家人', '个人的内心想法', 'EI', 'E', 'I'),
('大多数人会说你是一个', '非常坦诚开放的人', '重视自我隐私的人', 'EI', 'E', 'I'),
('你通常', '与人容易混熟', '比较沉静和矜持', 'EI', 'E', 'I'),
('在一大人群当中，通常是', '你介绍大家认识', '别人介绍你', 'EI', 'E', 'I'),
('你喜欢花很多的时间', '和别人在一起', '一个人独处', 'EI', 'E', 'I'),
('你认为别人一般', '用很短的时间便认识你', '要花很长时间才认识你', 'EI', 'E', 'I'),
('和一群人在一起，你通常会选', '参与大伙儿的谈话', '跟你很熟络的人个别谈话', 'EI', 'E', 'I'),
('你是否', '容易让人了解', '难于让人了解', 'EI', 'E', 'I'),
('在社交聚会中，你会', '是说话很多的一个', '让别人多说话', 'EI', 'E', 'I'),
('你是否', '可以与任何人按需要从容地交谈', '只是对某些人或在某种情况下才可以畅所欲言', 'EI', 'E', 'I'),
('我更倾向于', '坦率开放', '着重隐私', 'EI', 'E', 'I'),
('我更倾向于', '健谈', '矜持', 'EI', 'E', 'I'),
('选择较符合你的词', '朋友众多', '朋友不多', 'EI', 'E', 'I'),
('你更倾向于', '爱合群', '文静', 'EI', 'E', 'I'),

-- 感觉（S） vs 直觉（N）
('假如你是一位老师，你会选择', '以事实为主的课程', '涉及理论的课程', 'SN', 'S', 'N'),
('要做许多人也做的事，你比较喜欢', '按照认可的方法去做', '构想一个自己的方法', 'SN', 'S', 'N'),
('你会', '跟随一些证明有效地方法', '分析还有什么毛病，及针对尚未解决的难题', 'SN', 'S', 'N'),
('哪些人会更吸引你', '实事求是，具丰富常识的人', '一个思想敏捷及非常聪颖的人', 'SN', 'S', 'N'),
('你更倾向于选择哪组词', '肯定', '理论', 'SN', 'S', 'N'),
('你更倾向于选择哪组词', '实况', '意念', 'SN', 'S', 'N'),
('你更喜欢', '以事论事', '富想象的', 'SN', 'S', 'N'),
('你更倾向于选择', '真实的', '想象的', 'SN', 'S', 'N'),
('你更善于考虑事件的', '必然性', '可能性', 'SN', 'S', 'N'),
('你更倾向于选择', '事实', '意念', 'SN', 'S', 'N'),
('选择较符合你的词', '务实的', '理论的', 'SN', 'S', 'N'),
('选择较符合你的词', '合情合理', '令人着迷', 'SN', 'S', 'N'),
('你更倾向于选择', '制造', '创造', 'SN', 'S', 'N'),

-- 思维（T） vs 情感（F）
('你是否经常让', '你的理智主宰你的情感', '你的情感支配你的理智', 'TF', 'T', 'F'),
('你倾向', '重视逻辑多于情感', '重视感情多于逻辑', 'TF', 'T', 'F'),
('要做决定时，你认为比较重要的是', '据事实衡量', '考虑他人的感受和意见', 'TF', 'T', 'F'),
('选择更符合你的词', '公正', '敏感', 'TF', 'T', 'F'),
('选择更符合你的词', '远见', '同情怜悯', 'TF', 'T', 'F'),
('选择更符合你的词', '客观的', '亲切的', 'TF', 'T', 'F'),
('你更倾向于', '分析', '同情', 'TF', 'T', 'F'),
('选择更符合你的词', '有决心的', '全心投入的', 'TF', 'T', 'F'),
('选择更符合你的词', '客观的', '热情的', 'TF', 'T', 'F'),
('选择更符合你的词', '坚持己见', '温柔有爱心', 'TF', 'T', 'F'),

-- 判断（J） vs 知觉（P）
('当你要出外一整天，你会不会', '计划你要做什么和在什么时候做', '说去就去', 'JP', 'J', 'P'),
('当你有一份特别的任务，你会喜欢', '开始前小心组织计划', '边做边找须做什么', 'JP', 'J', 'P'),
('你比较喜欢', '很早便把约会、社交聚集等事情安排妥当', '无拘无束，看当时有什么好玩就做什么', 'JP', 'J', 'P'),
('当你要在一个星期内完成一个大项目，你在开始时候就会', '把要做的不同工作依次列出', '马上动工', 'JP', 'J', 'P'),
('总的来说，要做一个大型作业时，你会选', '首先把工作按步细分', '边做边想该做什么', 'JP', 'J', 'P'),
('在日常工作中，你会', '通常预先计划，以免要在压力下工作', '颇为喜欢处理迫使你分秒必争的突发事件', 'JP', 'J', 'P'),
('你认为按照程序表做事', '大多数情况下是有帮助而且是你喜欢做的', '有时是需要的，但一般来说你不大喜欢这样做', 'JP', 'J', 'P'),
('你做事多数是', '照拟好的程序表去做', '按当天心情去做', 'JP', 'J', 'P'),
('按照程序表做事', '合你心意', '令你感到束缚', 'JP', 'J', 'P'),
('你更倾向于哪个', '预先安排的', '无计划的', 'JP', 'J', 'P'),
('你更倾向于哪个', '有条不紊', '不拘小节', 'JP', 'J', 'P'),
('你更倾向于哪个', '预先安排', '不受约束', 'JP', 'J', 'P'),
('你更倾向于哪个', '决定', '冲动', 'JP', 'J', 'P');
