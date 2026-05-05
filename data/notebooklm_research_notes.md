# NotebookLM/Gemini 研究对话记录

日期: 2026-05-04
Notebook: beyesgp-高比例新能源电网WCS理论框架

---

## Q1: 多约束场景设计优化

### 回答

针对你在ANDES仿真中遇到的电压严重度（f_voltage）失去区分度的问题，这在暂态稳定评估中是一个非常典型的现象。根据你提供的第二轮实验结果[1]，在bus 7故障+Line_8跳闸时，f_voltage几乎恒定在0.997，导致其无法有效区分不同运行方式的安全裕度。

结合电力系统物理原理、Kundur系统的特性以及提供的安全域理论，对你的三个问题建议如下：

### 1. 哪些故障位置会主要产生电压问题？bus 9-10故障是否更有效？
**是的，bus 9-10（负荷母线）故障会产生显著更多的电压变化。**

*   **物理原理解释**（*基于Kundur系统特性的物理背景补充*）：在Kundur两区域四机系统中，bus 7、8、9构成了连接两个区域的弱联系联络线通道。发生在bus 7或线路8上的故障，主要削弱了区域间的有功传输能力，导致发电机转子加速，因此主要激发出**功角失稳（f_angle主导）**。相对而言，bus 9和bus 10是系统的主要负荷中心，消耗大量的有功和无功。当故障发生在bus 9或10时，会引起负荷母线电压的大幅跌落；由于该处缺乏足够的本地无功电源支撑，故障清除后容易出现电压恢复困难或延迟，从而大量触发**电压稳定问题（f_voltage主导）**。
*   **理论映射**：从安全域理论来看，不同位置的故障会使系统逼近不同的安全域边界。bus 7故障逼近的是动态安全域（D-SR）边界，而负荷中心故障则更容易逼近电压安全域（V-SR）边界[2]。

### 2. 如何设计故障集使得不同簇由不同约束主导？
要让聚类结果（簇）在不同约束上呈现主导性，你需要设计一个**包含异质性物理冲击的故障集（Contingency Set）**，而非单一线路故障。
基于新能源WCS理论[3]和安全域几何结构[2]，建议故障集包含以下三类典型场景：
*   **f_angle主导型（功角约束）**：保留当前的**跨区联络线故障**（如bus 7、bus 8故障并伴随跳线）。这类故障直接冲击传输极限，激发区域间振荡模式。
*   **f_voltage主导型（电压约束）**：引入**重负荷母线故障**（如bus 9、bus 10三相短路）或**无功补偿设备/发电机跳闸**。在负荷水平较高（如load=[1.0, 1.15]）且新能源出力比例较高时，这类故障会极大考验系统的动态无功支撑能力。
*   **f_freq主导型（频率约束）**：引入**大容量发电机跳闸或大负荷切除**（如丢失区域1的某台主力机组）。高比例新能源接入导致系统惯量降低[3]，有功功率的突变将直接由f_freq的响应来体现。

### 3. 是否应该使用多个故障位置的severities的加权组合作为最终指标？
**不建议简单使用加权平均组合，更推荐使用“最坏情况（Max）”或“基于信息熵的动态加权”。**

*   **避免简单加权组合**：如果将不同故障的severity进行固定加权（例如 $S_{total} = \sum w_k S_{fault\_k}$），会“平均化”危险信号。在电力系统安全评估中，系统的稳定性取决于**最薄弱的环节**（即距离综合安全域 $\Omega$ 边界最近的点）[2]。
*   **建议方案A：综合最坏场景（Max法）**
    针对设定的故障集 $K$，最终的 severity 应取所有故障中导致的最严重指标：
    $Severity_{final} = \max_{k \in K} S(fault_k)$
    这完全符合WCS（最坏场景搜索）寻找安全域边界上severity最大点的物理定义[2]。
*   **建议方案B：基于信息熵的动态权重调整（Entropy-based Weighting）**
    你当前采用的是固定启发式权重（w1=0.5, w2=0.25, w3=0.25），缺乏理论推导[3]。根据统一severity度量理论，可以利用**信息熵（Information Entropy）**来确定权重：$w_i \propto H(\phi_i)$，即**区分能力越强（方差越大、信息量越丰富）的指标，权重越高**[4]。
    例如，在你当前的实验中，f_voltage的std仅为0.0001[1]，其信息熵极低。如果引入动态加权，算法会自动降低该特定场景下f_voltage的权重，而在测试bus 9故障时，f_voltage的波动变大，其权重又会自动上升。

**下一步建议**：
你是否需要我详细列出基于“信息熵（Information Entropy）”来动态计算 $w_1, w_2, w_3$ 的具体数学公式，以便你能够直接整合到当前的Python/ANDES代码中？

### 参考资料

- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=1, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='376b1d63-a2c3-4773-b9f7-5a06bdf69bf9')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=2, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a001defb-858c-4160-9a43-527526202887')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=3, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='571b745f-4e2d-4b38-aaa8-ca0d20527fc1')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=4, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1a6ba446-d034-4a98-aeaa-134139d06d9e')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=5, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='63bff8c3-2fb1-4745-9840-d2a01dcdf9b1')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=6, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='baa8d330-676a-4474-9038-f22729674b97')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=7, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='887e8d63-1878-433b-9792-642a7b10f246')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=8, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='d4bbf2f2-f843-49c2-9ddc-7252593ae06a')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=9, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='dea09e4b-3571-4e9d-ab1c-050a14badf17')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=10, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='5b708083-5dc8-429d-876a-b74e30d86c8e')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=11, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='9cc511a7-9a43-4614-b833-5f26644d2aa6')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=12, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='086f381a-0b89-400b-8e33-85f16194e855')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=13, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='af55702b-1904-4006-8b96-1623f3ca070d')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=14, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='943d01bf-97c3-41da-a162-33b32d3a2fbf')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=15, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1bb202ba-ac6e-4199-b2e0-9ce98a5ae1e6')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=16, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8765c921-288d-4bfc-8aa3-b5c291936d93')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=17, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='31bde8af-0813-47a0-9f21-b2c12f69b5bf')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=18, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='e0051548-86d4-4d70-9a13-5620a2ebf923')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=19, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a475afb0-4914-413c-8b26-f3a10898162e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=20, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='232ebd1c-72b1-4de1-9353-272e978dad97')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=21, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='3880a2aa-700b-466e-9cc5-e7f1b0dc163c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=22, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='9916bb3b-568c-492d-accf-3a9c8c360715')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=23, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='49468b1c-9dd2-4f55-a8eb-3e6ac94ef3e7')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=24, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='f2a78dd3-9862-487d-86a1-651771d0fd24')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=25, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='88f83c68-d1cc-456a-860b-9d45ed878acf')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=26, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='c7571665-7671-4ebc-bfd7-d79e576e3ecc')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=27, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='f3c2e0bb-7633-4367-8ab3-d18031df02c6')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=28, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f62f5eed-8888-4f1f-a06f-df2154bf7dde')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=29, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='5f736bba-0caa-4189-9cef-485b880ea826')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=30, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c6f5f33a-33ab-4398-aff5-5680dc7b4bd8')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=31, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='c125e8db-7184-4ff7-971d-485b843c6a26')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=32, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='3e87ad66-1567-4cc3-ad00-e44eddeac7ed')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=33, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='97917299-b5b2-4dc7-be82-81894e26fd3d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=34, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8b24ec59-c851-4a2b-be6c-0de024064ccb')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=35, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='5948017b-9929-4eca-b355-f3e560927def')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=36, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='5f07170f-d12d-42c5-90b7-5323026556c2')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=37, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='954f4caa-9b40-421b-b5b2-dd91ca684a80')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=38, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='3e4c3cbc-3eed-4b69-977a-118d23215173')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=39, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='e177d988-7397-4dff-87e4-5d0407619359')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=40, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='0b4b78fe-8404-475f-95dc-fba2cc0b5729')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=41, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='194eb302-48e3-47be-995b-900e0842b795')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=42, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='b87d8b38-0592-4a1b-94be-4679cd16e2b8')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=43, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='7a8bbb08-017c-4c03-88b1-ef44db25de11')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=44, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='41da52c5-e48f-4dff-b550-07fe54442596')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=45, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='42361a1e-6e83-4e25-9b8a-f4fefbb22091')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=46, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='37fe4aeb-b73c-4262-83b6-d23e6f7e6d58')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=47, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='3ce43659-669a-48bf-99b6-2658e1428935')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=48, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='bcbc3706-653e-426f-8f4b-97cde627fadc')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=49, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='6c6b3a61-65f1-4226-9c2e-6b9fecf6b4ec')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=50, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ebf21534-b859-4d1e-b883-59c6ee906f3d')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=51, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='6d8adc43-85de-421f-8068-5a550028526a')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=52, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='fdd79559-d0e6-4e4e-88c0-b64b92983c75')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=53, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='2cfcb163-f5fb-4319-94a7-a3e8f01b2b66')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=54, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='5c5d5929-c204-48f8-8f5a-1a84d59543e8')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=55, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='0d2c07ef-d9ad-4ae2-a2ef-8041e92a12d5')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=56, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='7926ef4b-86dc-4899-8fff-b72252d68a54')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=57, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='84a992d2-2b2e-4815-b11b-4195a807ee46')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=58, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='50fa5afd-34d7-4fe8-bcc0-ebd8b2cf0e94')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=59, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='57847d0f-8af5-44d2-a0aa-49450f953291')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=60, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='ad66dd06-e126-49ba-99bc-23fbea67b64f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=61, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='0efe6c7c-1e99-4ae8-977f-62c58bde495b')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=62, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='d933fa09-260f-46f4-a323-11bd094d0efc')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=63, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='e774a8a8-3374-4783-9617-b88df1f59676')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=64, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='3603b26f-a6a4-4c3e-b475-b47cfca03058')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=65, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='9e39f3e1-657e-422f-b8d8-e3cede2abff3')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=66, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='e2b42671-5d94-4bb5-9fbe-602d0d84501d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=67, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='c6862242-0065-4c0c-bb27-6895723f2f3a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=68, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='dd7414dd-853f-45dd-ab9f-b2abc89f0707')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=69, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='536b10fb-01f9-43ed-a1cc-87b59bbb9bc3')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=70, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='a1027927-112e-436c-9438-756940798478')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=71, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='a4396751-f0a8-4829-99ac-e8c3223bbb1b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=72, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c8b9f363-a6b0-4aca-b78a-f0e6fee465e6')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=73, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='e404e8e1-b351-4116-8781-8ed42e684cd1')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=74, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='fa18d620-32d8-4b7a-a4ba-be5c5dede920')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=75, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='6ef8a899-e2e9-4937-b8a6-ce12655540a0')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=76, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='83e76a7b-5257-4f4f-9854-13e17ea90315')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=77, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1957d888-4111-4960-a3e3-87f9facd4ff9')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=78, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1594009f-6ab9-4110-830a-207e76665043')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=79, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='9ccf437f-a78a-4e19-aae6-429f182e9859')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=80, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='23bbdd2b-1a1c-439d-9b79-abc2cf82f6fb')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=81, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='d183339b-2b89-4909-8ad5-45afa6717e84')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=82, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='b41b9844-ef28-4555-aeee-2eb951bf1192')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=83, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='d70d267f-831d-4cc9-8159-e60f3f88ace9')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=84, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='43b5a27f-098a-48d4-9a49-53a7f31beb2f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=85, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='a8ca6934-b3e5-4d76-a33c-cc107cef9fd4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=86, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='b3b2627b-b509-422e-811e-e4691161263e')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=87, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='4e7f19f6-ffb3-4fb2-b50a-f1aeae9a8c27')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=88, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='0e87b9b9-8003-421f-a090-c5bd7303c9bd')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=89, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='4da8889c-01f7-4389-ad24-34fc03433501')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=90, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='014b0ef4-11b0-459b-8b8c-642c9e04b588')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=91, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='478149af-7397-4477-9975-33759dbb87cd')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=92, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='e35489ba-5c69-4e0e-998a-8f7ffbee7a15')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=93, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='ca6168db-266f-48f1-8e65-7a6c3d910d0f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=94, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1be83ba2-b191-42c1-a43d-a3cfa527a85d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=95, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='415e99c8-ded3-47f6-bab1-89b031bb1b90')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=96, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='29ae9b77-0234-4f3a-9ce8-0b4f4189ba90')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=97, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='efb874ed-62f8-4cd2-828f-955a70d66e01')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=98, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='8c0f49d5-57b8-4a2b-9747-2131b6d2df4c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=99, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='6773e1a2-6df9-48b5-b372-c5bc3932b14c')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=100, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1452b67e-e000-404a-8268-86ea6ad70c98')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=101, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='d5659f4c-ca57-41ec-8f39-5148f122420b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=102, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c4f7f13b-9eec-4de5-a00a-dc3b89627a1c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=103, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8f44f6f5-8c5e-448b-a68c-3bfcb5a49f85')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=104, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='685b894d-5f3f-4dc1-9d59-c29143da45e3')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=105, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='d09c88ae-13da-4bec-a957-66c20469d857')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=106, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='d17b7225-21cc-435f-afad-aa25bc685527')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=107, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='abef0915-6746-4026-a3ca-9627f8eb9970')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=108, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='8d77ce27-de20-46bf-a7e4-73a82741841a')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=109, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='179c00d7-5828-402a-82b9-a22da7424e9a')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=110, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a87367d0-9cc0-4004-86e0-203b883017c4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=111, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='45c505e2-71dd-4988-ad65-3bec2e1c3f6c')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=112, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='38dc4963-1287-44e9-9a59-c5a6735aa6db')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=113, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='79019c53-3dd2-4a2a-8d63-4f1c989ef399')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=114, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='8d9b9a70-9ed4-4af1-acb1-57ae58ae6d1e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=115, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='d8c51ca1-0cc3-4294-b797-8b39be718901')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=116, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='0acb7969-1c8f-4191-815f-0cbe8934a128')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=117, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='c4ab5795-c1ce-4a8d-9410-974ba0e1a958')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=118, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='8d9b9a70-9ed4-4af1-acb1-57ae58ae6d1e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=119, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='d8c51ca1-0cc3-4294-b797-8b39be718901')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=120, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='0acb7969-1c8f-4191-815f-0cbe8934a128')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=121, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='c4ab5795-c1ce-4a8d-9410-974ba0e1a958')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=122, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='8d9b9a70-9ed4-4af1-acb1-57ae58ae6d1e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=123, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='d8c51ca1-0cc3-4294-b797-8b39be718901')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=124, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='0acb7969-1c8f-4191-815f-0cbe8934a128')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=125, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='c4ab5795-c1ce-4a8d-9410-974ba0e1a958')

---

## Q2: 联合mode+fault空间的BO优越性验证

### 回答

你的实验设计方向非常清晰。结合提供的文献和你的第二轮实验结果，以下是针对你三个问题的具体分析和实验设计建议：

### 1. 量化9D联合空间中BO与对比算法的效率差异
你考虑的两个指标（达到90%最优的仿真次数、固定budget下的best severity）非常有说服力。为了在论文中更全面地展现理论与工程价值，建议采用以下指标体系：

*   **Simple Regret (简单遗憾)**：基于BO的理论基础[1]，这是最标准的学术评价指标。公式为 $R_T = \max(S_{true}) - \max_{t \le T}(S_t)$，其中 $\max(S_{true})$ 是你4500次全扫描得到的全局最高severity。
*   **固定Budget下的WCS命中率 (Top-K Coverage)**：由于电力系统安全评估往往需要找到多个危险场景，你可以定义全局最危险的前1%（即45个场景）为目标集。对比不同算法在固定仿真次数（如300次）下，能“揪出”多少个Top 1%的场景。这比单纯比较最高severity更能体现算法探索整个高危区域的能力。
*   **加速比 (Speed-up Ratio)**：即你提到的“达到X%最优所需的仿真次数”。建议设置两个阈值：90%最优（评估初步收敛速度）和99%最优（评估精确收敛速度）。用 RS 或 LHS 所需的平均次数除以 BO 所需的次数，得到明确的加速倍数。

### 2. Joint GP高R²是否直接证明联合搜索的必要性？
**不能直接证明。** Joint GP的 $R^2$ 显著高于Mode-only GP（当前为0.792[2]），仅能证明“模式(mode)与故障(fault)的联合输入与Severity之间存在更平滑的映射关系，GP能够很好地拟合这种高维流形”。

要直接证明**联合空间搜索的必要性**，你需要在论文中提供“**解耦搜索会陷入局部最优**”的证据（即交叉耦合效应）。建议增加以下论证：
*   **非线性交互证明**：提取两组不同的运行方式（例如高风电比例 vs 高负荷比例）。展示在这两组模式下，最恶劣的故障位置或故障类型是**不同**的。如果所有模式下最危险的故障始终是同一个（例如某条联络线短路），那么联合搜索就没有必要（退化为先找最差故障，再调最差模式）。
*   **主导失稳模式的切换**：你的severity是综合考量的（$w_1 \cdot f_{angle} + w_2 \cdot f_{freq} + w_3 \cdot f_{voltage}$）[3]。利用你第二轮的发现（$f_{angle}$和$f_{freq}$是主要区分指标）[2]，你可以证明：在特定风光组合下，某故障可能激发功角失稳（$f_{angle}$主导）；但在另一组合下，另一个故障可能触发频率崩溃（$f_{freq}$主导）。联合空间BO正是为了自适应捕捉这种复杂的边界[4]。

### 3. 收敛曲线对比实验设计与参数建议
为了让BO的优势在论文图中清晰、震撼地呈现，建议采用以下实验设置：

**总预算 (Budget) 与仿真时间设计：**
*   **全空间扫描（Ground Truth）**：4500次仿真 × 0.8秒 ≈ 1小时。这作为你的性能上限（Baseline/Oracle）。
*   **对比实验Budget**：建议设为 **250~300次仿真**（约为全空间的5%~6%）。
    *   在9D空间中，经验法则建议初始采样点（Initial Points）为维度 $D$ 的5到10倍。建议使用LHS进行 **50次初始化**。
    *   BO 迭代搜索 **200~250次**。
    *   单次实验耗时约4分钟。

**图表呈现设计 (Convergence Curve)：**
*   **X轴**：仿真次数 (Simulation Iterations)，0 到 300。
*   **Y轴**：当前找到的最大Severity (Max Severity Found so far)，或标准化后的目标值。
*   **置信区间 (极重要)**：由于RS、LHS、GA和BO的初始点选取具有随机性，**必须跑 10 到 20 个不同的随机种子(Random Seeds)**。在曲线上绘制各类算法的平均值（实线），并用浅色填充展示 $\pm 1$ 个标准差（Shaded area）。由于BO的定向探索能力，其方差通常会在几十步后快速收敛，而GA和RS的方差会很大，这能在视觉上强烈突出BO的稳定性。

**BO核心参数建议（针对确定性仿真器）：**
*   根据BO理论[1]，电力时域仿真器（如ANDES）的结果是精确无噪声的（$y=f(x)$）。如果不加处理，GP在观测点处的后验方差 $\sigma^2_n(x)$ 会归零，导致模型过拟合，停止探索。
*   **对策**：在GP的核函数中强制加入一个小的白噪声（Jitter / White Noise Kernel，例如 $10^{-4}$ 或 $10^{-5}$ 量级），或者使用带噪声观察的假设来训练GP，以此维持对已知点附近高危区域的持续探索[1]。
*   **采集函数**：建议选用EI（Expected Improvement）或UCB，且对于WCS搜索，可以适当提高UCB中的 $\beta$ 权值，鼓励算法多去探索高方差的未知边界，而不是过早陷入某个已知高severity的局部[5]。

你需要我为你进一步梳理如何在论文中撰写“确定性仿真器下BO加Jitter的理论依据”部分，或者讨论具体的采集函数选择吗？

### 参考资料

- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=1, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='b5eea4db-2f99-4b40-8783-3311ebfe1992')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=2, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='473e65ef-cfbb-454c-8c86-0c411aa25a88')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=3, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='111801d5-fcf8-4692-813b-ed21a133b141')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=4, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='6dd44351-5eb7-43d0-85f8-07907ab68967')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=5, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='ba65405b-89f2-4fe9-82c4-8662b43b2fe8')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=6, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='6fdfa535-1bc3-493e-b200-7067e2fbefd2')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=7, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='4adf03de-480c-41a8-aa4e-a0989fdbd7c5')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=8, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='2c13b4a3-4252-4635-b7e6-e82026626324')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=9, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='24138605-7c2d-4b07-8641-3e5febcf0a3c')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=10, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='b694c0e4-4202-4fb7-a930-39104c394cef')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=11, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='0c052a3d-5d38-449f-93ff-0cf5afe681ce')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=12, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='4629833a-4e07-4571-8765-892b8c6b2b0e')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=13, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='e9d97834-a4e1-402c-8f6b-85385291ee91')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=14, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='bfb6c2b5-d23c-4228-8702-2dfa0d4aab06')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=15, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='45714308-5bc2-40fc-a919-fa6d0f232592')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=16, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='097640cb-99f2-4c6f-a564-872612b55d9d')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=17, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='ce29be39-05f7-4883-994f-91576c9a03dd')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=18, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='6056d742-3e72-49f6-9c3c-4d26c9fb7773')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=19, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='069d88cc-1952-41d8-ac58-c74178743f51')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=20, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='ed2a49f6-760b-4cb8-ba5e-3c5b50b82f59')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=21, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='6feff5d4-4825-418c-8d02-3504d53058b8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=22, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='61aa7416-5f1b-47ae-b7c6-cb7a0ec00b57')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=23, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='05f0f792-b9f4-422f-a6e4-4c8fc81ad5f9')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=24, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='c6abb4ad-61ec-4f35-ad88-b8a5f9d4c7f1')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=25, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='82540fce-afce-4bd4-9e07-56da58f37212')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=26, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='4bfa51ba-15b5-4b30-aaa9-203aa9a588d5')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=27, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='de3d7404-d89e-46bb-a589-a1d36aaf8121')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=28, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='78184e04-3f80-4735-958e-6f46fa573701')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=29, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='1a619da5-1505-4c66-b5dd-95dce7b9b8f8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=30, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='221deee1-b17f-42e1-9076-35b7e1eb5268')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=31, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='d8e0f4c2-4958-4b5d-92ac-1fedc2b7dd01')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=32, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='38d54c81-35c5-43b5-912a-5db44ed4d4ad')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=33, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='b5f13b85-3d89-4590-a7e9-f25c0fe973ba')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=34, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='eff4e35e-9f33-46a2-b8d6-738a533b105a')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=35, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='57474040-8312-4b8b-bc66-9743ea5ef62f')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=36, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='34c13efe-7a20-4851-b018-6e0ad35c5ab3')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=37, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='7f3bb907-432e-4eff-a4d9-e6aaf6252ec5')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=38, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='ba1f540f-7e84-47a6-92fc-a8976bb2eb60')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=39, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='6660bf7a-dadd-400c-9a6e-0bf1e5efdfe7')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=40, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='8612f83a-e0d3-4c41-8394-5b8b1ee34022')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=41, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='ac725122-a58a-4b87-9dee-783cb72d0abd')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=42, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='817b9bb9-a5a5-4c92-ab24-27c100274752')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=43, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='12225b47-10bb-457f-a0b8-e358de8268aa')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=44, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='86204643-6f08-44b0-803a-c23751f9ddc1')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=45, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='a11669c8-e2cf-454b-95fb-bc113dc4fd79')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=46, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='bfd80ab1-3c1f-430c-9b0d-5db039156954')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=47, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='2479e32e-52b1-44d1-8c9f-01cb739016ed')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=48, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='cbb97cae-eb4f-44f6-a8dc-d772d0693c99')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=49, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='7ceccefb-5cfd-4413-b30f-42c6e7d11b0d')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=50, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='daf8713f-d0e6-4870-a640-ec2bf3a77d5c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=51, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8e532d27-2df9-41e4-8fb8-aa54f729d038')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=52, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='2976eaa0-267c-4e19-a9ae-f3c7466d6738')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=53, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='f6851733-4e01-4641-8de9-c61d1248c415')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=54, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='4d892b5c-cc82-469c-b91e-db2d20f1f3d3')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=55, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='775e462f-7b41-4a83-9e3e-7cf6d8da9f53')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=56, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='642da425-c4a3-478d-86f3-37e02e682e69')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=57, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='705d5980-9090-487a-9259-b70894a3f0b7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=58, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ffb33ef4-e3f7-4b46-b236-f3c172a05ebe')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=59, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='7348ad05-aa84-4b50-928c-f878aa9b22dc')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=60, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='a33f278e-8019-4f21-8452-3d25e25c5060')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=61, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='dc980b48-bdcb-4a6b-a38a-bc7a2f443c5d')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=62, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='7e3257c1-cec8-40da-b3d4-2a0b24adaeec')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=63, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='fbb5f6e1-8f1b-4bf6-a466-64a1b038ba76')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=64, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='0f0c4bd5-ee27-42af-9e09-aa78afcaf08a')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=65, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='603d706e-a07a-4152-82b5-2b76bbcf3948')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=66, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='8caf99bd-d9d4-4c86-9909-d369a902db42')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=67, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='12f1e5a5-0266-466d-9928-feba1f7ccc66')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=68, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='208138a4-37f7-4340-b047-5846bc3ed6d4')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=69, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='e5fd7a75-9203-4ba2-a205-06b1a64ac139')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=70, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ed91ea7f-02db-46c9-9667-e65936befcc7')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=71, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='87fa3acc-c199-4e02-962a-637c8fa86f9d')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=72, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='b3e089d9-00a2-45c3-89f6-da51d4f56696')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=73, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='65c81ac9-9db1-433e-8d8c-e82558a876f9')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=74, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='47b5c651-b1d4-4650-aa99-9d8a79b98f12')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=75, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f5e6db26-9da4-430e-81e6-b0e3750d1288')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=76, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='ab6d8a6f-684a-4f34-88ae-e69fb41725f9')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=77, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='f8174401-ff66-45f8-85b8-e7b69664847a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=78, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1dd06089-e60f-4b3e-ad35-d70e5dd20136')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=79, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='90cde9cb-d997-4710-a4d4-036d76dd51f1')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=80, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='88a286a3-f35f-4a97-a758-41fd2b99471c')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=81, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='03bb869c-3de5-4c48-aa97-695a0ed7d290')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=82, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='83af3161-4347-446c-820a-f0123fb0339c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=83, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='a6e8b594-aa17-44e7-bb91-895ad7a2492f')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=84, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='52aac869-adc7-4d50-aa57-256a76781f1a')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=85, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='9a291ad3-570d-4b2c-9644-57878f6c53f8')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=86, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='f989a221-46cc-4deb-a577-cf535fe11d71')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=87, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='ff357697-fbfb-40b8-8d5b-8bf26f5f5ff2')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=88, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='fae3f240-a6bb-4c82-8358-84a427b75645')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=89, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='a81c8db1-9963-4f80-9f14-0a508e85ce27')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=90, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='c7ae94ee-f6a3-4e16-8b09-bf4a0f19df21')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=91, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='08dc54dd-5385-472c-8862-606d7aae3e7d')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=92, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='57a214e7-56d5-4ed4-9148-6552a5a823ef')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=93, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='44012f71-852e-4ae4-8f70-fee643a9b894')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=94, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1e4521ae-a368-4b0c-86d9-b09046bd01f2')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=95, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='14974a1f-7b93-48c1-9769-f843f3f42bb3')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=96, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='01d19a78-e8fc-48cd-a370-ced9666abe6e')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=97, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='004484a4-b986-460d-95ff-eb642f27cf77')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=98, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='372d9520-a8c7-4f55-a11f-2e7e109964ef')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=99, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='e15d4443-a6bb-42ad-a089-677473f6969a')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=100, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='21672073-bea5-4fd6-8ec9-32cf78346d2a')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=101, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='8d34b2d1-c5cc-4327-ba08-86875f0dde1f')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=102, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='6aaf9169-51bc-4633-a8c4-1488adaed64b')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=103, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='a2a22f09-4a22-4a0d-b6af-3677a4a93e48')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=104, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='9bd47da0-11fb-48f2-889e-4fdae2900a2d')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=105, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='2ca50ef3-7e4a-4cc9-8402-4318cc7767a3')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=106, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='8b535fe7-e704-406e-ae32-36e348f2f6cd')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=107, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8f082468-7140-4d53-92d4-5d5f4aab114e')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=108, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='a429d682-409c-4b68-a946-83d20a063761')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=109, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='f9e9092f-8fba-445b-87fd-d03fe221add7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=110, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1e4291a3-4e0a-4de0-be88-c3c889cf94d2')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=111, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='22d8970e-55fd-4149-a0f8-aca9fa78ae06')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=112, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='ca8984b8-02fe-4c12-af90-8e5e7aca92f5')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=113, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='73b9ddb7-b9d6-422e-910f-f0d1c50bc3eb')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=114, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='4b6066ff-20c1-40ac-bd07-8ff074af4112')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=115, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='7d15ef79-9eba-4d96-8eb2-4cf5d984a8f9')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=116, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='97b6f28f-2ed4-4536-ac13-af18ceebb234')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=117, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='1125a76e-d0c6-4fa5-83d9-db7692390fc4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=118, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='6884331b-7b2d-42f5-94f1-a73bb8d6075f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=119, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='dc823fc3-ff68-4ac3-817a-3975d9b785b9')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=120, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='b8a883fb-6f4b-442f-a499-a5e48a8e23ce')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=121, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='e1531a8b-cf0c-4d8b-b61b-0e4a8ae0bbcb')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=122, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='798371a9-ed09-4eb3-87d9-60d8b333ccdc')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=123, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='b0ff5790-d9e4-449e-aa6f-45c2b62c0e87')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=124, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='c8259a02-c260-44af-a66c-a6d37e379cc7')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=125, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='03a3e52d-6abb-402c-9751-d9abbb15093a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=126, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='132a4026-6a10-4034-a444-ec579fd9e83e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=127, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='609e55c9-6a41-4265-9773-80e3908262eb')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=128, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='954ae4f3-62b7-41f3-9f14-6dea1367258d')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=129, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='0d6bba8b-b2e6-4503-80ce-686fed334583')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=130, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='5fb6a12f-b2ec-40a4-8fd9-b4887b0b3fdd')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=131, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='ed7648e2-1fcd-4578-bd26-e04e255bed9f')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=132, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='480352fc-f84e-4ddc-abf6-3ceb151aace8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=133, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='22198b92-50ce-4f76-bc44-11ecf2e064f4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=134, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='dab14028-c175-4a52-820e-594bb39f54ed')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=135, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='9c6da412-6505-429f-8320-f5a51f8ecba1')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=136, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='03c9231b-72ed-4001-a79d-56f59fb73713')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=137, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='f0bb5d06-5624-465e-9164-ba6445eae25d')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=138, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='58a29382-e718-43d5-a804-addab5a97d48')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=139, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1c2ecd61-1a16-4bdc-b729-3f7516391eec')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=140, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='6bc9b133-46c5-43ef-9cce-8a739b1a84a1')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=141, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='17db9c8e-178c-4a14-8109-7466b8cf9d7e')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=142, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='d2f167a2-68de-493d-8d86-13cbb9d12fd0')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=143, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='95cc200a-4a13-4470-a901-2a696ef595bf')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=144, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='7bd5d250-79ac-400a-b9fa-f9f09c5b67c4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=145, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='552e867a-e690-41b0-9ca6-c58f347bd0cf')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=146, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='8b174ba9-6a54-4f42-89bf-a301c5979382')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=147, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='d2f167a2-68de-493d-8d86-13cbb9d12fd0')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=148, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='95cc200a-4a13-4470-a901-2a696ef595bf')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=149, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='7bd5d250-79ac-400a-b9fa-f9f09c5b67c4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=150, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='552e867a-e690-41b0-9ca6-c58f347bd0cf')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=151, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='8b174ba9-6a54-4f42-89bf-a301c5979382')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=152, cited_text='贝叶斯优化与鲁棒优化理论', start_char=0, end_char=12, chunk_id='d2f167a2-68de-493d-8d86-13cbb9d12fd0')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=153, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='95cc200a-4a13-4470-a901-2a696ef595bf')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=154, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='7bd5d250-79ac-400a-b9fa-f9f09c5b67c4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=155, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='552e867a-e690-41b0-9ca6-c58f347bd0cf')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=156, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='8b174ba9-6a54-4f42-89bf-a301c5979382')

---

## Q3: 频率约束的差异化利用

### 回答

针对您关于Kundur系统频率约束的三个问题，以下是从电力系统物理角度及现有理论框架进行的分析：

**1. 频率偏差的影响因素与高比例新能源的直接作用**
在电力系统暂态稳定中，高比例新能源的接入确实会直接导致更容易出现频率偏差问题。随着风电、光伏等新能源装机占比的快速提升，传统同步发电机被大量替代，这会带来**系统惯量持续降低，以及频率调节能力的下降**[1]。从物理角度来看，系统惯量是抵抗系统频率突变的核心物理量。在低惯量条件下，当系统发生故障导致瞬时有功功率不平衡时，系统频率变化率会显著增加，从而使得高比例新能源（如Cluster 4的低惯量/高RE场景）面临更严峻的频率稳定挑战[1, 2]。

**2. 双约束代替三约束的合理性**
在当前场景中，采用 `f_angle` + `f_freq` 双约束代替包含 `f_voltage` 的三约束是**非常合理**的。
在统一severity度量的理论推导中，赋予各项稳定指标权重（$w_i$）的方法之一是基于**信息熵**（$w_i \propto H(\phi_i)$），即区分能力越强的指标应该获得越高的权重[3]。实验结果明确显示，在设定的bus 7故障+Line_8跳闸场景下，`f_voltage` 的均值为0.997且标准差仅为0.0001，几乎处于恒定状态，完全失去了区分能力[2]。相对而言，`f_angle`（std=0.271）和 `f_freq`（std=0.198）展现了极好的区分度[2]。剔除无信息量的 `f_voltage`，不仅符合信息熵赋权的理论原则，还能避免在多约束优化中稀释关键约束（功角和频率）的引导作用[2, 3]。

**3. 触发频率问题的故障位置与发电机母线故障的影响**
关于发电机母线（bus 2-4）故障的具体影响，**目前的资料中仅记录了 bus 7故障+Line_8跳闸 这一场景下的实验数据，并未包含发电机母线故障对频率影响的直接仿真结果**[2]。
不过，从安全域和暂态能量理论来看，系统的稳定性与暂态能量裕度（TEM）密切相关，而能量的积聚直接取决于故障期间的物理冲击[3, 4]。如果故障发生在发电机母线附近，在物理上会直接且严重地阻碍发电机的有功功率输出，产生极大的瞬时有功不平衡。在系统惯量本就因新能源接入而降低的背景下[1]，这种大规模的有功不平衡必然会对全网频率产生更剧烈的冲击。

您是否需要我为您搜索更多关于“Kundur系统发电机母线故障对暂态频率影响”的最新文献资料，来进一步验证这一推论？

### 参考资料

- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=1, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='5b4f5c26-b213-46fb-bb5b-a41898248666')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=2, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1d19baa5-dfec-418f-a8b8-bcd21800118b')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=3, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='2ff7268e-7561-4449-8d54-c8d5bc3bc585')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=4, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='99620211-a7db-43da-bfd8-61573f5deb0c')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=5, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='78ebe577-d42c-40a3-8de4-65aeecb7b0a7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=6, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='9467f334-42c6-47ef-be7f-8b9470c32cda')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=7, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='501f66f6-67e4-465f-b484-d524ee4cf5a4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=8, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='13245f5c-83eb-451b-822b-6814124fc27b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=9, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='04221f61-082c-4ada-9afa-f2ae1d535156')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=10, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='c3524bb4-fd76-451a-b200-5ac332e5272e')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=11, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c69f0747-22c3-4974-af06-ee88b8c34da7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=12, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='e7f754e4-6d16-41a2-b6f4-8b296dbd4086')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=13, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='d8bc4fce-5ecd-4f28-a76a-e923124420cc')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=14, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='72ed2165-e23d-472e-ab45-ba02b32b587b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=15, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='000e266d-4749-43d1-93b7-b2774bab666e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=16, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='8ab0ebc0-1e8b-43ee-aa56-402542e8f6d7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=17, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='e73dcc86-4e70-49bc-94e4-7449c5778455')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=18, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='b6f813bd-7cf6-4d59-9fdb-9a8a8ad5ab58')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=19, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='8d50afc4-72d1-4a0d-ae17-236d257fb764')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=20, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='98548312-536f-4b3d-adf2-094cdf6d7b8e')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=21, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='fd86109b-afe0-42bd-a216-765b2f81e57b')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=22, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='57e8ccd7-2a49-42bd-af93-027b83e29aa3')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=23, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='0d6c2b6f-4c84-4e2e-95db-de806bc41bea')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=24, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='825890f4-00fe-49e6-b2f7-e35eb33bcd7c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=25, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='278e2bb7-b56b-4752-8105-1d106dabcaae')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=26, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='80f4e658-aaa6-4a69-afdc-edfabff00789')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=27, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='910b0409-8ed2-48cb-84bd-a30bae81f0f0')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=28, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='0f1823bc-7734-466f-9c49-548a95042560')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=29, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='16460c56-6ea6-4a96-892f-3213e0402344')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=30, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='79e52b9e-ade0-47e7-b29a-a5f0927ca9ae')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=31, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='32ccfa94-df0c-43c3-beae-edbd8656699a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=32, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='da631503-33d1-49c3-867c-c87d448f76ae')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=33, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c9465bc2-b54e-4fc9-a5f4-f5e5a4a463f2')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=34, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='54ccc6cd-6be2-4496-9711-8e7a1bc9d355')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=35, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='5f86aaa0-ca28-4f96-bab9-1bb8d51c14e4')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=36, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='778a550b-a0c9-4dc0-b0a8-b00ff6171dca')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=37, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='35ab7c53-fcbf-4c12-993e-12d946fdcda5')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=38, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='75e890cb-eb9c-461d-92fb-fb380de434c8')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=39, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='bad3eceb-787e-484d-a1ae-a6b80ba06543')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=40, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='634b8d62-9ad5-441a-87a6-45cb27cb9c57')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=41, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='50aa8812-0366-40fd-8528-f3238843529b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=42, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='b4c97a83-8e74-4552-9e02-ac2aef967df7')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=43, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='bfdb6205-8a53-4b03-893e-f96a357e812e')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=44, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='fdef8cf1-df90-47c9-9c6a-d02ff411243b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=45, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='bf52dd95-add6-40f1-bba6-7afe18e977cf')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=46, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='b3ddf765-7bec-42ec-a066-47fcbf45b1ef')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=47, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='7da43b2a-ef9a-490c-b5f9-990c110efa66')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=48, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='4974e1f5-58b9-4610-81c8-242851772cd6')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=49, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='0f979fb2-66d0-4adf-a596-3b9b540944aa')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=50, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='14ec2a74-f0da-4da5-8d7e-b98b162bf778')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=51, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='3bd9d672-8899-433e-b7bb-2cde0c403c04')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=52, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='4b9a614b-edec-4f91-b5e0-7f04cc4a5f2b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=53, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='4a97a325-d252-4b28-b7c2-610f4f20b265')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=54, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='bee1498c-3973-42a2-9ec7-0f2fd4317e7c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=55, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='d691ebab-b593-4baa-b1bc-475207c590a0')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=56, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='c77aaf5b-5481-4c62-ae94-d800494dd0dd')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=57, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='387acd43-ec88-46b9-8e5b-5e92cfa47784')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=58, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='8c64bcbe-2baa-4680-85de-4b177aef92be')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=59, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='70d9d4c5-7865-4632-87c0-fc37f366c7f8')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=60, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='60e34439-54cc-4bae-b4ec-82323aba4ece')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=61, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1344487c-cb6c-43e9-907f-0c0a5a8a96ea')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=62, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='10ad05ac-510a-4285-bfef-74e5ff6bf900')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=63, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='50feae30-355f-44af-8fec-caeb1cebaa4f')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=64, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ce817d35-d44a-495c-abe1-14dce33e5633')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=65, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='9c1595fc-b1c3-44b9-b95a-3f2146a54b94')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=66, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='2098ac23-9021-4108-aa4c-7881b8abfd2f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=67, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='5da77a02-8078-4e73-92fa-1092dfd8be8b')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=68, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ce817d35-d44a-495c-abe1-14dce33e5633')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=69, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='9c1595fc-b1c3-44b9-b95a-3f2146a54b94')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=70, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='2098ac23-9021-4108-aa4c-7881b8abfd2f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=71, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='5da77a02-8078-4e73-92fa-1092dfd8be8b')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=72, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ce817d35-d44a-495c-abe1-14dce33e5633')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=73, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='9c1595fc-b1c3-44b9-b95a-3f2146a54b94')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=74, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='2098ac23-9021-4108-aa4c-7881b8abfd2f')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=75, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='5da77a02-8078-4e73-92fa-1092dfd8be8b')

---

## Q4: 论文实验设计优化

### 回答

针对您的论文实验设计，结合文献资料，以下是具体的优化建议：

**1. 关于如何让更多簇获得有意义的分档限额提升**

**强烈建议选择方案 b（使用 per-constraint 独立映射和自适应权重）**。

*   **理论支撑**：根据安全域理论与统一severity度量，severity度量的权重确定方法中明确包含了**“信息熵：$w_i \propto H(\phi_i)$（区分能力越强权重越高）”**[1]。
*   **数据印证**：您的第二轮实验数据完美契合这一理论。`f_voltage`几乎恒定（std=0.0001），说明其信息熵极低；而`f_angle`（std=0.271）和`f_freq`（std=0.198）具有很强的区分度[2]。
*   **具体做法**：不应使用缺乏物理意义的Sigmoid数学强行拉伸（方案a），而应在论文中提出一种**基于信息熵（或方差）的动态加权severity度量机制**。在计算最终的severity或限额时，自动为`f_angle`和`f_freq`分配高权重，降低`f_voltage`的权重。这不仅能解决其他5个簇区分度低、提升较小的问题[2]，还能填补原方法中“severity度量是启发式加权的，缺乏理论推导”的理论不足[3]。

**2. 论文还需要补充哪些对比实验？**

除了您计划的收敛曲线、分档提升和维度扩展外，为了说服审稿人，建议补充以下核心实验来凸显方法的物理意义和理论深度：

*   **独立采样 vs. Copula相关性采样对比实验**：审稿人通常会质疑极端场景在物理上是否可能发生。您可以通过对比传统独立采样（如LHS）与基于Copula的新能源空间建模生成的场景，证明传统方法可能找到“物理上不可能”的假边界，而您的Copula方法能生成“物理一致”的危险场景[4]。
*   **“概率加权最坏场景”风险偏好（$\alpha$ 与 $\beta$）对比**：利用公式 $\xi^* = \text{argmax} P(\xi)^\alpha \cdot S(\xi)^\beta$[5]。设计一组实验，调整风险偏好参数（例如，对比激进策略$\alpha \to 0$ 和保守策略$\alpha \to 1$），展示不同风险偏好下的寻优结果差异，这将极大提升文章的工程实用价值[5]。
*   **GP代理模型在确定性仿真中的防过拟合策略实验**：BO在确定性仿真器中因为没有噪声（$\varepsilon=0$），极易发生插值过拟合[6]。建议补充一个实验，对比“标准GP”与“增加微小噪声核(jitter)”的GP在寻找WCS时的准确率或RMSE指标（目前您的R²=0.792，RMSE=0.066[2]），以证明您的BO设置针对无噪声仿真器进行了理论上的正确适配[6]。

**3. 如何在论文中定位 "voltage恒定" 这一发现？**

**应该将两者结合，但以“论文的Contribution（发现物理特征并推动算法演进）”为主线进行包装。**

*   **作为安全域特征的揭示（Contribution 1）**：结合电力系统安全域理论，WCS是在安全域（$\Omega$）边界上severity最大的点[7]。`f_voltage`在bus 7故障+Line_8跳闸下几乎恒定为0.997[2]，这揭示了该特定故障轨迹是**平行于电压稳定域(V-SR)边界的，而直接切入并穿越了功角稳定域(D-SR)和频率稳定域边界**[7]。说明BO-WCS方法具有很强的物理透视能力。
*   **作为引出改进算法的动机（Contribution 2）**：将这个现象作为您引入“基于信息熵自适应权重的多约束映射”（即上述方案b）的**直接动机**。您可以这样写：“实验发现静态多约束加权在遇到局部平行安全边界（如恒定的电压响应）时会失效（局限），*因此*，本文提出了一种基于信息熵的动态自适应映射机制（贡献）[1]。” 这样就把一个负面的实验现象完美转化为了新方法提出的依据。

您是否需要在论文中深入展开关于 Copula 模型构建（用于生成物理一致的新能源场景）的具体数学公式和实验步骤？

### 参考资料

- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=1, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='c08321eb-4a15-484a-99d4-5f4923f3462d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=2, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='5de903a5-b0a2-46da-a950-f6275a35ad61')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=3, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='8f6ac23f-5992-404c-8bee-1905f066191e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=4, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='acace373-8ea2-4a4c-9aac-9c55077c9086')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=5, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='27cdb318-5ea0-4401-b47e-475d282ca4f8')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=6, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='99c2034a-881b-4362-9f22-be63dcd788d8')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=7, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='96c1597e-87a0-415a-8370-d008d842a89a')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=8, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='956d2649-4c89-4df5-b611-3708bfe287b9')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=9, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='aa156b23-7f2c-4b2e-8f1f-f2d3f02b1349')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=10, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='26141aed-ee85-4d0e-a60e-50030dca2a4f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=11, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='47a6199c-d8e4-4d79-831e-b76d998908b4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=12, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='59885932-a496-4f24-b8a9-a05a637c5f25')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=13, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1eee6293-22f4-46ec-9315-027ab8cd320c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=14, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='bb54aef2-bc6b-40e6-8f8f-4fa9b116a5e2')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=15, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='01319fd6-cdeb-4f93-b66e-46c7a16ca2e4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=16, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='8358a8b1-f16d-4a89-bc75-9ed7db46095e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=17, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='5951d5bb-24cb-40c9-b6c7-8d4899f0f331')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=18, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='d733f554-37e7-4dd9-af40-075e4b131345')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=19, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='23ad4eaf-0fc5-48a8-90e9-e07d2516c945')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=20, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='9e723f6a-10db-4f91-888a-7fd822e01da6')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=21, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='28901167-0681-48c7-8dd0-58be7e8391a8')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=22, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='1105cd89-7c57-4a34-b348-78e26267218b')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=23, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='6ae49bef-8b0b-4454-8154-560b42b2ea07')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=24, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='27e14cdd-3d86-4f0a-bf04-7d398f1aeb26')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=25, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='17f3c9b4-39f1-41ae-9b3c-6343139d33ec')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=26, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='a5cda289-1331-47ba-a45e-110819694ae5')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=27, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='7a1cda8e-444a-4821-a552-1a57ff00e1ec')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=28, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='3e4a99eb-035c-48df-aa41-eccbfd9552cb')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=29, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='f9dc50b6-fc27-4ace-a90b-1ee4b99a2648')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=30, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='c5547b32-f823-4e6d-b95c-23acf96a591a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=31, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='26d6662d-7a49-492f-8f1e-ba14257c8e68')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=32, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='d8096a38-898e-4778-a408-4815efe6bcc9')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=33, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='a6b60258-f550-4ea4-bf72-819b8943133d')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=34, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='002ea03b-3274-4213-8494-43c9e127facc')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=35, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='27495a9b-517d-4418-b23f-ba49b4485fb5')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=36, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='26cbf965-4077-4e2c-859e-dd81e11208e4')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=37, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='380ad272-d1d4-4e01-90cf-d110acbe59d5')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=38, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a88d8cdf-81b9-44af-ad6d-274a36c968ec')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=39, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='f5d3a07c-67d4-40a3-a76a-eba5317ac168')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=40, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='e9b71452-80e9-45c0-8ae6-7db57364f729')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=41, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='b2974f1a-5745-4430-a8f4-3ac57a9ae0bc')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=42, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='10a4c122-a29b-4855-96d7-9842e2c429b7')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=43, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='17cda81c-8e8d-4efe-b6dd-7fb5ab056b5f')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=44, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='b455c4a1-ebe2-4d72-a8aa-3ed7c312ef0c')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=45, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='bbbe2807-b393-48c2-b073-f70bb1de2ff9')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=46, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='1bdcfd37-69b6-4016-b850-61f4aa486430')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=47, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='8e4b7ffb-2dc7-4fe8-9500-b6cf7254c3c1')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=48, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='068dada9-a764-4a8a-a700-edbd5a4add5a')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=49, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='9c2a538f-1956-4759-8d2a-c086a7ca1f30')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=50, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='83c42509-221c-4340-aa11-d97cab238595')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=51, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='de32bbb2-3f8d-40b6-b458-b0c8eb6349f1')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=52, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='627617ca-0aa3-4032-becc-baa0e0c5e9c1')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=53, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='5999b127-1aba-40ad-98f2-ed41a905c1f9')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=54, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='8d3d095b-1511-432b-89b9-39ca002728ac')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=55, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='1c0b0f85-caf8-4f90-a28f-55bca85dbec8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=56, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='fb216cf7-b09e-45b2-8bda-10650dee6169')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=57, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='e80bbaca-dab9-4d56-addd-378a72e8cf9f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=58, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='e200488e-5956-44a3-930a-5d31d0863c87')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=59, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='ff8a44b4-3d7c-476b-abd1-702235abcfea')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=60, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='e6fef480-00d5-479f-86c2-2532adb5723b')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=61, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='090ef8bf-e10c-4d5b-96b6-15f147379253')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=62, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='662d94c3-0997-49d8-a39c-15138c12b3ce')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=63, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='47054809-4c72-4c0f-945b-43d6c7a59be7')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=64, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='6289ab23-b902-4b0d-875f-33720b74ca72')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=65, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='a6083fec-2352-4067-94df-cb7caca14397')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=66, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='51586cdc-2211-449f-8433-3bb30794372c')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=67, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='ea5720aa-a40c-434b-96f6-f9ac459e3697')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=68, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='e1555b5c-d32b-4eb0-87d8-554439b0bd52')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=69, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='281b8c97-d030-4400-add6-3760f49cf2b0')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=70, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='0e6f6a8b-7abc-4409-aed9-d632ff5a32b8')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=71, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='6375dd10-4bdb-48af-9069-001a051fcd51')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=72, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='3b667a73-3676-42ac-96be-fbee9df76524')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=73, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='2441da1c-724b-40f8-a8e3-13dd65b3ae14')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=74, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='c04432ce-25cb-4f6c-b2cd-e95d2adc0c23')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=75, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='a903b52b-8ec6-4d2e-bac1-bc625c95f53d')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=76, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='ebbdb483-4c32-4130-828d-7f2c4fb9a0b4')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=77, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='a7fe1bf7-e28d-4617-94c4-e440629dd84f')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=78, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='b10ba1b8-7814-4e4b-8b6d-1544dc1a7769')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=79, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='e88ecf9f-0d69-4550-8108-b69ff2f95c8e')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=80, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='5a2623d2-da99-461e-9f87-382fa4b4018a')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=81, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='16d86f45-0781-4fa2-9d1d-ef4882cba196')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=82, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='4d100e67-b876-4549-8963-25cc861e2b29')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=83, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='3536c0a9-13f5-4a10-b12c-a2cd93b3947a')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=84, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='e91a05d2-326d-4a5a-bc36-43370a3761e8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=85, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='9868ee14-81cb-436c-a5b6-b001e212ec5b')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=86, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='858f8746-fba2-49f0-8068-16c4a3be1fdf')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=87, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='1a71f359-c403-4aa4-be7c-2d88fde8cfea')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=88, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1a6c26ee-eb50-45e5-9010-b1995798b2fd')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=89, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='65213eac-82d9-43bb-ba84-675c9e170634')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=90, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='ff2253ea-0f2a-4804-b4c7-689f0eff19f2')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=91, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='a542cb5c-0a4a-4ebf-a365-3ccd56dfb1a7')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=92, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='eae9213f-9a43-4102-839a-415e82414ff9')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=93, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='1f3154f5-51a2-479b-be85-8e16ea135b4d')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=94, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='b8ecad23-3a03-4ac6-92b7-dd42c7aca2ac')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=95, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='50bd03e6-04b0-419e-846e-f10cf134f6c9')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=96, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='e6c1ded8-d996-45a1-b8f0-cdf0be38630f')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=97, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='a840028e-11f9-4e40-ab86-a63639c4b5b2')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=98, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='bace1e06-e599-4252-a9e4-f0eae90d7475')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=99, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='024f0559-323a-4c91-80cd-d8ab49097066')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=100, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='1725d9d1-019d-4680-afad-5d5e71aea08d')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=101, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='214eac0a-7b31-4e2b-b9bc-028b00f58bbe')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=102, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='8a3d0511-7699-4900-8592-09f00b849cba')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=103, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='91a1a598-aa0c-4b76-9277-100ff8607b6c')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=104, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='f080fd13-b7df-4116-b47b-c545b8fc6a28')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=105, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='2100f084-29ef-4cc5-897f-58a370e6ed3b')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=106, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='5c9729e9-31ed-489f-a042-590ce70cee21')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=107, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='3ad8d7fc-83a5-4baf-a6ff-337d76a89953')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=108, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='eb5337ec-932c-4745-a26a-20c2d530b0a8')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=109, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='dac4dff1-8e69-40cf-a493-60d7bf6d82b9')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=110, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='d7027608-bbd0-49ec-80c1-b4b82d76b1ee')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=111, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='995f16d3-1d63-4d46-8495-2d3e0d4e8c08')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=112, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='552d0259-f551-4865-8765-bd71165e1dd7')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=113, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='e9c96984-fc9e-4ac3-b095-be104c742cab')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=114, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='bb1c3078-da28-4965-9b29-70224ba0901b')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=115, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='d455abab-e891-4e45-aeb0-cc2538657f73')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=116, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='457d4187-ede4-4474-9f13-67f2da95946d')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=117, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='b5f99999-f913-45b8-a6b1-7e66ce79670f')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=118, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='5ecaa5aa-c47a-4436-9915-0c92fd740e42')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=119, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f1a2870c-52b7-4216-96e7-c4e99615c284')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=120, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='5d760e26-6efd-45b4-93cd-5c54305d6c65')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=121, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='247bacdb-ceb5-4666-801a-a0406fa5798e')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=122, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='9ecd8b72-741e-4b31-9ba7-da67a4fd0d93')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=123, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='909c10b3-2f20-42db-bafc-00658a217daf')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=124, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='6bd1abd4-d7f5-459f-8a3b-87d55b008fed')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=125, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='1ec1afcd-476c-4be7-ab19-3af77e0a6ddb')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=126, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='00288a18-80c9-41a7-8bc6-9ec55a930136')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=127, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='ca60d381-f987-485a-a4d0-2c56bcfbe71b')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=128, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='ea9dd880-6205-4bca-b93f-9293e651a640')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=129, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='0c42287f-3baf-40a7-8bfc-39312c3fd8cc')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=130, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='49829cc0-6efe-4e2b-a940-5303ddcbc8ba')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=131, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='7c931b4e-082f-467f-9613-193eede36b1f')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=132, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='61ef3dff-bbbc-4398-9b34-f4530db09301')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=133, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='8e9ad52c-6081-428c-946e-3a3ea21f369e')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=134, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='d3355b5f-f2ff-44b8-95c3-4f9432cecd4a')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=135, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='10dc4aca-ade6-48c7-81e0-ccf8f7b982a7')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=136, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='2ea22da3-4a55-41c2-bfff-4da505d0484c')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=137, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='7bb1ffc6-df22-46ef-9063-1caf801c9498')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=138, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='9a8205e5-af06-49f6-a6f1-4ef760c7792a')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=139, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='067ca63c-8aac-4fae-b202-981b288e2f90')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=140, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='07f9afc1-96ac-492e-854e-b8803545e4ee')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=141, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='163dfc39-e57f-4578-a5b9-5656c0af4017')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=142, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='95168058-1eb6-4569-a256-fc3ba26d2392')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=143, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='d59486e7-284a-4d0a-9211-efdff8876367')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=144, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='7302483a-9e09-450b-9d32-948dac41ea16')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=145, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='560174cb-07cf-48e4-bcd5-fec021dcdeef')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=146, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='0681b774-c355-4499-b49d-dbed82447a0c')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=147, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='9ef02570-9c4b-4fa4-a904-b85b746f958d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=148, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='bb84cf08-e42d-4d9b-963b-4cc2085a7da9')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=149, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='6b1949c9-5207-4325-8d0e-4824c52eb993')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=150, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='9ba11cbf-e9f2-49aa-87c3-ce90f6903361')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=151, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='b9d1ee34-7d74-489f-8d96-3fc81d922a2c')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=152, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='2dbc40f1-6a59-4528-be5b-8253a6ebdd25')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=153, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='645a3b8e-9d81-4652-924f-9f6380be13ca')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=154, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='22039cb3-06bb-4eb3-8f23-7575ba94c3a8')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=155, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='0996a7dc-262f-4f64-be06-74a5567fd138')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=156, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='48c5d384-c741-4471-98d9-88a859aa51e1')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=157, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='e1678f59-50a9-47d3-acf0-1d4d32e34961')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=158, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='c9dd44cc-dbd0-4755-9544-a71a74cea9ce')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=159, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='28e79506-cbf3-4a04-9c21-a7b03b02b268')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=160, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='7d75bfd8-835e-4d18-8907-806483fdc8ef')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=161, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='500960ab-2551-4b3a-a88c-b1010e48c33b')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=162, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='1901cf09-9009-496d-b885-b6d4b10680a3')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=163, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='369c4f04-663e-4990-a498-d73ad5459cc2')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=164, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='50e85bee-3fe8-4f91-b28d-448cd9ac454f')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=165, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='d0e5068c-d06c-450b-9ba2-4097050fa6e0')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=166, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='fe40af20-c150-4f67-8af9-e093d0c7dd57')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=167, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='693f0a36-a207-49fc-9299-f411db65d04d')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=168, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='af91cf1c-da49-465b-a0ef-57f2d30b3e68')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=169, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='580e7e87-f7ea-44b8-873d-3ce45e13580f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=170, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a9756b64-7c91-4f79-a4e8-05f2e892cfa1')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=171, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='dda68a82-986d-4036-b32d-6d6641017301')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=172, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='48be02a5-340b-490f-99a1-fff462c1dd22')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=173, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='dffc70b2-86d2-4b98-a2ea-0445aa7d2425')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=174, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='392d61cd-6a2c-42bd-bd0d-8e01fe699b77')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=175, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f37c642a-544e-4701-933f-c923f329c730')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=176, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='580e7e87-f7ea-44b8-873d-3ce45e13580f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=177, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a9756b64-7c91-4f79-a4e8-05f2e892cfa1')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=178, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='dda68a82-986d-4036-b32d-6d6641017301')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=179, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='48be02a5-340b-490f-99a1-fff462c1dd22')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=180, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='dffc70b2-86d2-4b98-a2ea-0445aa7d2425')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=181, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='392d61cd-6a2c-42bd-bd0d-8e01fe699b77')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=182, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f37c642a-544e-4701-933f-c923f329c730')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=183, cited_text='TEM > 0 → 稳定', start_char=535, end_char=547, chunk_id='580e7e87-f7ea-44b8-873d-3ce45e13580f')
- ChatReference(source_id='23fde1c7-f497-4ad4-b7c6-bd4a3917c9a1', citation_number=184, cited_text='=== beyesgp 第二轮实验结果摘要 ===', start_char=0, end_char=25, chunk_id='a9756b64-7c91-4f79-a4e8-05f2e892cfa1')
- ChatReference(source_id='ea63053d-9947-4797-80ea-af549d450578', citation_number=185, cited_text='高比例新能源电力系统暂态稳定最坏场景搜索', start_char=0, end_char=20, chunk_id='dda68a82-986d-4036-b32d-6d6641017301')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=186, cited_text='Copula理论与新能源时空不确定性', start_char=0, end_char=18, chunk_id='48be02a5-340b-490f-99a1-fff462c1dd22')
- ChatReference(source_id='f07c88b0-4999-475b-9c6a-70b923929bea', citation_number=187, cited_text='"概率加权最坏场景"定义', start_char=564, end_char=576, chunk_id='dffc70b2-86d2-4b98-a2ea-0445aa7d2425')
- ChatReference(source_id='93199b97-1b41-45f1-8111-6f62e926670b', citation_number=188, cited_text='BO-WCS的理论定位', start_char=558, end_char=569, chunk_id='392d61cd-6a2c-42bd-bd0d-8e01fe699b77')
- ChatReference(source_id='359a3bb0-12ec-412d-9199-2b3c9c4cd0f5', citation_number=189, cited_text='电力系统安全域理论', start_char=0, end_char=9, chunk_id='f37c642a-544e-4701-933f-c923f329c730')

---

