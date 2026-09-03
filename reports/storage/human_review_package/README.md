# STAGE8 G2/G3/Dedup — ChatGPT 动态审核包
- TREECUT_G2_CHATGPT_REVIEW_V1.mp4 (206.9s, 720x1280): 20 Queries; 每候选=CONTEXT BEFORE 0.7s + SELECTED WINDOW + CONTEXT AFTER 0.7s; 顶部标签含 query/TOP/segment/subclip/machine action/motion(WEAK|MODERATE); 不显示机器GOOD/BAD
- TREECUT_G3_CHATGPT_REVIEW_V1.mp4 (90.3s): 16 Beats; 卡含 SCRIPT/STORY_MODE/REQUIRED; 候选同三段结构
- TREECUT_DEDUP_CHATGPT_REVIEW_V1.mp4 (40.9s): 4 对(真实V2镜头); A/B 各三段; 无侧对(见说明)
判定输出格式: G2 每 Query Top1-3 GOOD/BAD/UNSURE+best+complete+boundary; G3 每Beat GOOD/BAD; Dedup TRUE_DUPLICATE/FALSE_POSITIVE/UNSURE
JSON: *_V1.json (machine 字段; human_result=null)
