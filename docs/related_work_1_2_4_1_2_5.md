# 1.2.4 RAG 知识投毒攻击与防御研究

目前国内外针对 RAG 知识投毒的研究主要包括面向检索语料的定向知识污染、面向触发机制的通用后门式污染、面向多模态检索增强系统的跨模态污染，以及面向投毒场景的鲁棒防御与溯源方法。其中，面向检索语料的定向知识污染方法通过向外部知识库、网页语料或企业文档中插入少量伪事实文本，使污染片段在用户查询时进入 Top-K 检索结果，并进一步诱导生成模型输出攻击者期望答案。Zou 等人提出的 PoisonedRAG 系统刻画了知识投毒同时依赖“被检索到”和“影响最终答案”两个条件的攻击机理，表明少量高相关污染文本即可显著改变 RAG 输出[6]。Deng 等人提出的 Pandora 则从 RAG 场景下的越狱与污染角度说明，攻击者可以利用检索增强链路绕过单纯面向提示词的安全过滤[7]。Chaudhari 等人提出的 Phantom 进一步研究通用触发式攻击，使污染内容不再只依赖固定问题，而能在特定触发条件下影响多类检索增强生成任务[8]。Liu 等人提出的 Poisoned-MRAG 将知识投毒扩展到多模态 RAG，说明图像、文本等多源证据混合后，污染内容可能通过跨模态相似性和证据融合过程进入最终回答[9]。这些工作共同表明，RAG 知识投毒不是普通文本错误，而是发生在“检索排序—证据选择—答案生成”链路中的复合型信息污染。

针对上述威胁，现有防御方法主要包括静态过滤与数据清洗、鲁棒检索与聚合、攻击溯源与安全 RAG 框架等方向。静态过滤与数据清洗方法通常依据黑名单、文本异常、来源可信度或重复片段比例排除可疑文档，适合发现明显广告、重复站群或格式异常内容，但对伪装成权威文档、与查询高度相关且语义流畅的污染片段识别能力有限。鲁棒检索与聚合方法尝试在检索阶段降低被污染片段支配答案的概率，例如 RobustRAG 研究在检索污染条件下为 RAG 输出提供可证明鲁棒性思路[11]，Towards More Robust RAG 则从对抗投毒评测角度比较不同检索增强系统在污染语料下的稳定性[13]。Benchmarking Poisoning Attacks against RAG 对攻击、防御和评测设置进行系统比较，说明不同投毒比例、Top-K 设置和检索器类型会显著影响防御效果[12]。攻击溯源方法则关注错误答案形成后如何回溯污染来源，Traceback 将投毒攻击溯源到候选污染文档或片段，为后续隔离和责任定位提供依据[10]。同时，Towards Secure RAG 等综述从威胁模型、防御手段和评测基准角度总结了安全 RAG 面临的系统性挑战[14]。

然而，现有方法仍存在三方面不足。第一，静态过滤和来源评分更关注文档是否“看起来可疑”，难以判断某个 Chunk 是否真正导致错误答案，容易把高频正常知识、热门政策条款或合法转载内容误判为污染。第二，鲁棒聚合方法通常依赖多数干净证据或检索结果相对独立的假设，当攻击者通过站群互引、复制改写或多源同义污染制造“伪多数证据”时，单纯投票或相似度聚合可能反而放大错误结论。第三，溯源方法多在错误已经发生后定位候选来源，若缺少与隔离、重检索和可信重生成联动的闭环机制，仍难以支撑竞赛 Demo 中“发现—解释—处置—恢复”的完整流程。针对上述问题，本文提出面向 AI 搜索与企业 RAG 的知识投毒检测与可信纠偏机制：首先以 RAS 衡量 Chunk 的异常检索吸附性，以 GIS 衡量 Chunk 对最终答案的生成诱导性，并通过 DualRisk 仅将同时满足检索异常与答案诱导的证据列为候选风险；随后引入四路反事实验证区分“相关片段”和“真正致错片段”；最后结合 Chunk 隔离、风险感知重检索和可信重生成，将检测结果转化为可解释、可执行的安全处置闭环。

# 1.2.5 反事实因果验证、图谱溯源与可信证据裁决研究

目前国内外关于 RAG 输出可信性的研究主要包括反事实因果验证、图谱化来源溯源、引用可验证性评价以及声明—证据裁决等方向。其中，反事实因果验证方法通过删除、保留或替换候选因素，观察系统输出是否发生显著变化，从而区分统计相关与真实致错因果。在 RAG 知识投毒场景中，仅凭某个 Chunk 与答案相似，不能说明它导致了错误；只有当“保留该 Chunk 时错误持续、删除该 Chunk 后错误缓解、仅使用该 Chunk 时错误复现、替换为可信证据后答案恢复”时，才能更有力地说明其具有因果贡献。现有 Traceback 等溯源研究已开始关注从错误输出回溯污染来源[10]，但若缺少反事实比较，溯源结果仍可能停留在候选相关证据层面，难以证明候选 Chunk 与错误答案之间存在直接因果关系。

图谱溯源研究则通过结构化节点和边表达信息来源、证据引用、转载复制、语义相似和答案依赖关系。GraphRAG 将图结构引入检索增强生成，用于组织实体、关系和社区摘要，从而提升复杂问题下的全局信息整合能力[22]；GraphRAG 综述进一步总结了图增强检索在结构化知识表示、关系推理和多跳问答中的作用[23]。这些研究说明，图结构能够比线性 Top-K 列表更清晰地表达“文档—片段—声明—答案”之间的依赖关系。但普通 GraphRAG 主要服务于问答质量提升，并不天然区分正常引用、无意错误、转载扩散和恶意知识投毒；若直接将图谱用于安全检测，仍需要引入风险边、因果边、隔离事件和来源独立性等安全语义，才能支撑污染传播路径解释。

可信证据裁决研究主要从引用正确性、事实一致性、声明验证和 RAG 忠实度评价等角度展开。Liu 等人针对生成式搜索引擎的可验证性评价指出，带引用答案不仅要内容正确，还需要引用能够真正支持相应陈述[16]。Gao 等人的 ALCE 关注带引用长答案生成，为答案片段与外部证据之间的可验证对应关系提供评测基础[17]。RAGAS、ARES 等框架从上下文相关性、答案忠实度、答案正确性等维度自动评价 RAG 系统表现[18][19]；FActScore 将长文本拆分为原子事实并逐一验证，为细粒度事实裁决提供思路[20]；FEVER 则以支持、反驳和证据不足三类标签构建事实验证任务范式[21]。RAGTruth 面向 RAG 幻觉与忠实度标注，为检索证据不足、证据矛盾和模型生成偏离等问题提供了数据基础[26]。此外，Trustworthiness in RAG 与 Towards Trustworthy RAG 等综述从可靠性、可解释性、鲁棒性和安全性角度总结可信 RAG 的关键问题[24][25]。

然而，上述研究在面向知识投毒防御时仍存在局限。引用评价和事实验证能够判断“答案是否被证据支持”，但通常不回答“哪条污染证据导致了错误”；图谱增强方法能够组织复杂关系，但如果缺少反事实因果分和风险处置边，难以直接用于投毒隔离；可信度评分方法能够衡量答案质量，却容易忽略来源独立性、复制传播和伪多数证据造成的系统性偏差。针对这些不足，本文提出将反事实因果验证、异构投毒传播图谱和可信证据裁决统一建模：在反事实层面构造原始 Top-K、删除可疑、仅可疑、可信替代四路答案，并计算 CausalScore 判断候选 Chunk 的致错贡献；在图谱层面建立 Page、Document、Chunk、Query、Claim、Answer 六类节点及包含、检索、支持、矛盾、复制、相似、致错和隔离等关系边，刻画污染从来源到答案的传播路径；在裁决层面构建 Claim-Evidence Matrix，结合 NLI/启发式判断、来源独立性、DualRisk 与 CausalScore 计算 TrustScore。相比单一事实核查或静态溯源方法，该机制既能解释错误答案“由谁导致、沿何路径传播”，也能将因果确认结果用于高风险 Chunk 隔离、风险感知重检索和可信重生成，从而形成面向 RAG 知识投毒的可解释可信恢复闭环。

# 参考文献

[6] ZOU W, GENG R, WANG B, 等. PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models[C]//Proceedings of the USENIX Security Symposium. 2025.

[7] DENG G, LIU Y, WANG K, 等. Pandora: Jailbreak GPTs by Retrieval Augmented Generation Poisoning[J/OL]. arXiv:2402.08416, 2024.

[8] CHAUDHARI H, SEVERI G, ABASCAL J, 等. Phantom: General Trigger Attacks on Retrieval Augmented Language Generation[J/OL]. arXiv:2405.20485, 2024.

[9] LIU Y, YUAN Z, TIE G, 等. Poisoned-MRAG: Knowledge Poisoning Attacks to Multimodal Retrieval Augmented Generation[J/OL]. arXiv:2503.06254, 2025.

[10] ZHANG B, XIN H, FANG M, 等. Traceback of Poisoning Attacks to Retrieval-Augmented Generation[C]//Proceedings of the Web Conference. 2025.

[11] XIANG C, WU T, ZHONG Z, 等. Certifiably Robust RAG against Retrieval Corruption[J/OL]. arXiv:2405.15556, 2024.

[12] ZHANG B, XIN H, LI J, 等. Benchmarking Poisoning Attacks against Retrieval-Augmented Generation[J/OL]. arXiv:2505.18543, 2025.

[13] SU J, ZHOU J P, ZHANG Z, 等. Towards More Robust Retrieval-Augmented Generation: Evaluating RAG Under Adversarial Poisoning Attacks[J/OL]. arXiv:2412.16708, 2024.

[14] MU Y, HU H, LI F, 等. Towards Secure Retrieval-Augmented Generation: A Comprehensive Review of Threats, Defenses and Benchmarks[J/OL]. arXiv:2603.21654, 2026.

[16] LIU N F, ZHANG T, LIANG P. Evaluating Verifiability in Generative Search Engines[C]//Findings of the Association for Computational Linguistics: EMNLP. 2023.

[17] GAO T, YEN H, YU J, 等. Enabling Large Language Models to Generate Text with Citations[C]//Proceedings of the Conference on Empirical Methods in Natural Language Processing. 2023.

[18] ES S, JAMES J, ESPINOSA-ANKE L, 等. RAGAS: Automated Evaluation of Retrieval Augmented Generation[C]//Proceedings of the EACL System Demonstrations. 2024.

[19] SAAD-FALCON J, KHATTAB O, POTTS C, 等. ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems[C]//Proceedings of the Annual Conference of the North American Chapter of the Association for Computational Linguistics. 2024.

[20] MIN S, KRISHNA K, LYU X, 等. FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation[C]//Proceedings of the Conference on Empirical Methods in Natural Language Processing. 2023.

[21] THORNE J, VLACHOS A, CHRISTODOULOPOULOS C, 等. FEVER: A Large-scale Dataset for Fact Extraction and Verification[C]//Proceedings of the Annual Conference of the North American Chapter of the Association for Computational Linguistics. 2018.

[22] EDGE D, TRINH H, CHENG N, 等. From Local to Global: A Graph RAG Approach to Query-Focused Summarization[J/OL]. arXiv:2404.16130, 2024.

[23] HAN H, WANG Y, SHOMER H, 等. Retrieval-Augmented Generation with Graphs (GraphRAG)[J/OL]. arXiv:2501.00309, 2025.

[24] ZHOU Y, LIU Y, LI X, 等. Trustworthiness in Retrieval-Augmented Generation Systems: A Survey[J/OL]. arXiv:2409.10102, 2024.

[25] NI B, LIU Z, WANG L, 等. Towards Trustworthy Retrieval Augmented Generation for Large Language Models: A Survey[J/OL]. arXiv:2502.06872, 2025.

[26] NIU C, WU Y, ZHU J, 等. RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models[J/OL]. arXiv:2401.00396, 2024.
