import asyncio
import os
import re
import sys
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, '/Users/mac/Developer/Summit/Otomatisasi Checksheet')

from sqlalchemy import select, update
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, ActivityLog

USER_RAW_TEXT = """
[Checksheet Incoming TSEY.xlsx](https://drive.google.com/file/d/1MCaWA27bubWvqnbSN7QuEBTe7VM0HaPU/view?usp=drive_web)
Part No. : 65191-TSE-X000-50[1](https://drive.google.com/file/d/1MCaWA27bubWvqnbSN7QuEBTe7VM0HaPU/view?usp=drive_web)
[CS IQC 5251D663 ok.xlsx](https://drive.google.com/file/d/1c1KadZmkouENX_sgQQrT0MM2KKiKVjcG/view?usp=drive_web)
Part No. : 5251D662[2](https://drive.google.com/file/d/1c1KadZmkouENX_sgQQrT0MM2KKiKVjcG/view?usp=drive_web)
[CS IQC 65141_TRDZ.xlsx](https://drive.google.com/file/d/1Ylu3VC7Gl2RWoZfrBAqtvrc7tjn6YdDC/view?usp=drive_web)
Part No. : 65141-TRDZ-K000-H1[3](https://drive.google.com/file/d/1Ylu3VC7Gl2RWoZfrBAqtvrc7tjn6YdDC/view?usp=drive_web)
[CS IQC 65141_TE7.xlsx](https://drive.google.com/file/d/1UrNGnVXnqNWj-fcAVPDN-27RHaEqV6vI/view?usp=drive_web)
Part No. : 65141-TE7-K000-H1[4](https://drive.google.com/file/d/1UrNGnVXnqNWj-fcAVPDN-27RHaEqV6vI/view?usp=drive_web)
[CS IQC 65191_TRDZ.xlsx](https://drive.google.com/file/d/1WBAluVtxwU-wEJCWxzeTxURy2kDez2hr/view?usp=drive_web)
Part No. : 65191-TRDZ-P000-H1[5](https://drive.google.com/file/d/1WBAluVtxwU-wEJCWxzeTxURy2kDez2hr/view?usp=drive_web)
[CS IQC 5253AU21 ok.xlsx](https://drive.google.com/file/d/1xgQuVzyf98OsHBS0LWq39TR0qJPPkkCV/view?usp=drive_web)
Part No. : 5253AU21/ 5253AU22[6](https://drive.google.com/file/d/1xgQuVzyf98OsHBS0LWq39TR0qJPPkkCV/view?usp=drive_web)
[CS IQC 65191_TE7.xlsx](https://drive.google.com/file/d/199KgFBqWjoPziJJr-8gCXfVA1mGSG2TT/view?usp=drive_web)
Part No. : 65191-TE7-K000-H1[7](https://drive.google.com/file/d/199KgFBqWjoPziJJr-8gCXfVA1mGSG2TT/view?usp=drive_web)
[CS IQC 5273A078 ok.xlsx](https://drive.google.com/file/d/1Q3sfnRFvv0jEzXH2DnsJxodnJEM2T2Go/view?usp=drive_web)
Part No. : 5273A078[8](https://drive.google.com/file/d/1Q3sfnRFvv0jEzXH2DnsJxodnJEM2T2Go/view?usp=drive_web)
[CS IQC 65191-TG4 -U000-50 ok.xlsx](https://drive.google.com/file/d/1ydlTC_Q4857TlyqedGLwW38wJRjmakvp/view?usp=drive_web)
Part No. : 65191-TG4 -U000-50[9](https://drive.google.com/file/d/1ydlTC_Q4857TlyqedGLwW38wJRjmakvp/view?usp=drive_web)
[CS IQC 5253AL07 ok.xlsx](https://drive.google.com/file/d/1zg3E83bGQfjBvNGVKbSk3HUI2xR-u6l4/view?usp=drive_web)
Part No. : 5253AL07[10](https://drive.google.com/file/d/1zg3E83bGQfjBvNGVKbSk3HUI2xR-u6l4/view?usp=drive_web)
[CS IQC 5257A792 ok.xlsx](https://drive.google.com/file/d/1piM8jjDfgfu4zn18pbrzMn8oNuv3UCGW/view?usp=drive_web)
Part No. : 5257A792[11](https://drive.google.com/file/d/1piM8jjDfgfu4zn18pbrzMn8oNuv3UCGW/view?usp=drive_web)
[CS IQC 5251D676 ok.xlsx](https://drive.google.com/file/d/1EDMH4wkQZydQfISTOScn43ddEV2E5sLC/view?usp=drive_web)
Part No. : 5251D676[12](https://drive.google.com/file/d/1EDMH4wkQZydQfISTOScn43ddEV2E5sLC/view?usp=drive_web)
[CS IQC 5290D396 ok.xlsx](https://drive.google.com/file/d/1V9_7ylV3mMIMd3zwxDhYUl2Ag1Uf5k5U/view?usp=drive_web)
Part No. : 5290D396[13](https://drive.google.com/file/d/1V9_7ylV3mMIMd3zwxDhYUl2Ag1Uf5k5U/view?usp=drive_web)
[CS IQC 5257A794 ok.xlsx](https://drive.google.com/file/d/1Inmew_OGg-gehhDFBGfWq1UMyS2CEKNl/view?usp=drive_web)
Part No. : 5257A794[14](https://drive.google.com/file/d/1Inmew_OGg-gehhDFBGfWq1UMyS2CEKNl/view?usp=drive_web)
[CS IQC 65761-TG4R-T001-50.xlsx](https://drive.google.com/file/d/1fGDK85KevyLX9y2Il66QQAkpxtj0rtVO/view?usp=drive_web)
Part No. : 65761-TG4R-T001-50[15](https://drive.google.com/file/d/1fGDK85KevyLX9y2Il66QQAkpxtj0rtVO/view?usp=drive_web)
[CS IQC 65192-TG4R-T000-H1.xlsx](https://drive.google.com/file/d/1iJPrGISaVIkNbmSAVzHeY-TaB0vpZ5dj/view?usp=drive_web)
Part No. : 65192-TG4-T000-H1[16](https://drive.google.com/file/d/1iJPrGISaVIkNbmSAVzHeY-TaB0vpZ5dj/view?usp=drive_web)
[CS IQC 5220G398,K869 ok.xlsx](https://drive.google.com/file/d/1UrHwEzUIv1MFsHKgEEciWjXNLFG-fXH7/view?usp=drive_web)
Part No. : 5220G398/ 5220K869[17](https://drive.google.com/file/d/1UrHwEzUIv1MFsHKgEEciWjXNLFG-fXH7/view?usp=drive_web)
[CS IQC '63915_T7A.xlsx](https://drive.google.com/file/d/18AxOv_OKe3l1_IFSqVXfID9IAC7pL7X9/view?usp=drive_web)
Part No. : 63915-T7A -3000-50[18](https://drive.google.com/file/d/18AxOv_OKe3l1_IFSqVXfID9IAC7pL7X9/view?usp=drive_web)
[CS IQC 5257A788,790 ok.xlsx](https://drive.google.com/file/d/1Q-7WeZyj4djlxEBkYFAmGpm7dwVk8TCn/view?usp=drive_web)
Part No. : 5257A778 / 5253A790[19](https://drive.google.com/file/d/1Q-7WeZyj4djlxEBkYFAmGpm7dwVk8TCn/view?usp=drive_web)
[CS IQC 63915-TG4R-T002-50 ok.xlsx](https://drive.google.com/file/d/1yqVz5wT0qCZoZ8x2gBi-1QpB4nj5b4J9/view?usp=drive_web)
Part No. : 63915-TG4R-T001-50[20](https://drive.google.com/file/d/1yqVz5wT0qCZoZ8x2gBi-1QpB4nj5b4J9/view?usp=drive_web)
[CS IQC 5257A778 ok.xlsx](https://drive.google.com/file/d/13CVeLASCyK35Fh-dexYxyBLT36Oo6B0B/view?usp=drive_web)
Part No. : 5257A778[21](https://drive.google.com/file/d/13CVeLASCyK35Fh-dexYxyBLT36Oo6B0B/view?usp=drive_web)
[CS IQC 5305A771,772 ok.xlsx](https://drive.google.com/file/d/1__jjaYHfx_6lLGgkWIpmr6ZFTYDV0mzf/view?usp=drive_web)
Part No. : 5305A771/5305A772[22](https://drive.google.com/file/d/1__jjaYHfx_6lLGgkWIpmr6ZFTYDV0mzf/view?usp=drive_web)
[CS IQC 63915-TG4-T000-H1 ok.xlsx](https://drive.google.com/file/d/1V_ajOijZ2J9h0ARmuWsWXv-ueSUEiiCI/view?usp=drive_web)
Part No. : 63915-TG4R-T001-50[23](https://drive.google.com/file/d/1V_ajOijZ2J9h0ARmuWsWXv-ueSUEiiCI/view?usp=drive_web)
[CS IQC 64621_T5L.xlsx](https://drive.google.com/file/d/15opgxEyyctE2XS6hvmrvy2z229zL-FsY/view?usp=drive_web)
Part No. : 64621-T5L -T000-50[24](https://drive.google.com/file/d/15opgxEyyctE2XS6hvmrvy2z229zL-FsY/view?usp=drive_web)
[CS IQC 5290D397 ok.xlsx](https://drive.google.com/file/d/1iPUV5NYUQ5bduTeO-aH7Ru4Y35u0T2tv/view?usp=drive_web)
Part No. : 5290D397[25](https://drive.google.com/file/d/1iPUV5NYUQ5bduTeO-aH7Ru4Y35u0T2tv/view?usp=drive_web)
[CS IQC 5290D373 ok.xlsx](https://drive.google.com/file/d/1pAGRDe1XIYtK5t-ti6_WPILNPerW9l33/view?usp=drive_web)
Part No. : 5290D373[26](https://drive.google.com/file/d/1pAGRDe1XIYtK5t-ti6_WPILNPerW9l33/view?usp=drive_web)
[CS IQC 5260A194.xlsx](https://drive.google.com/file/d/1aYDS-25u94Et_rOUtcZKXsmMXqbcS-H4/view?usp=drive_web)
Part No. : 5360A194[27](https://drive.google.com/file/d/1aYDS-25u94Et_rOUtcZKXsmMXqbcS-H4/view?usp=drive_web)
[CS IQC 5253AH19 ok.xlsx](https://drive.google.com/file/d/1jYu5o3j9Db04SI2IxOWDfVIhDytf2wQA/view?usp=drive_web)
Part No. : 5253AH19[28](https://drive.google.com/file/d/1jYu5o3j9Db04SI2IxOWDfVIhDytf2wQA/view?usp=drive_web)
[CS IQC 5290D374 ok.xlsx](https://drive.google.com/file/d/1IaRfL0mUC-gNR6A76qVx0I_6Gya_agrx/view?usp=drive_web)
Part No. : 5290D374[29](https://drive.google.com/file/d/1IaRfL0mUC-gNR6A76qVx0I_6Gya_agrx/view?usp=drive_web)
[CS IQC 65791-TG4R-T001-H1.xlsx](https://drive.google.com/file/d/1MrQfzpOqUHemWcXvfpi9m5U24X6CAUQ-/view?usp=drive_web)
Part No. : 65791-TG4R-T001-H1[30](https://drive.google.com/file/d/1MrQfzpOqUHemWcXvfpi9m5U24X6CAUQ-/view?usp=drive_web)
[CS IQC 5290D387.xlsx](https://drive.google.com/file/d/1k-GssvxSFfL0Y3hnQar4r5fbvf8prtNh/view?usp=drive_web)
Part No. : 5290D387[31](https://drive.google.com/file/d/1k-GssvxSFfL0Y3hnQar4r5fbvf8prtNh/view?usp=drive_web)
[CS IQC 65761 -TG2 -K001-50.xlsx](https://drive.google.com/file/d/1UK41c694YErzwKxU-RYX7skqSx1kdhBM/view?usp=drive_web)
Part No. : 65716-TG2-K001-50[32](https://drive.google.com/file/d/1UK41c694YErzwKxU-RYX7skqSx1kdhBM/view?usp=drive_web)
[CS IQC 63915_TE7.xlsx](https://drive.google.com/file/d/1En4Zw2TaN0JqZOdU3odXJifzrgSkGhvK/view?usp=drive_web)
Part No. : 63915-TE7 -K000-50[33](https://drive.google.com/file/d/1En4Zw2TaN0JqZOdU3odXJifzrgSkGhvK/view?usp=drive_web)
[CS IQC 5253AU19,20ok.xlsx](https://drive.google.com/file/d/1IadtliUg-t7Vp_HEbZpmluImeCASGcyG/view?usp=drive_web)
Part No. : 5253AU19/5253AU20[34](https://drive.google.com/file/d/1IadtliUg-t7Vp_HEbZpmluImeCASGcyG/view?usp=drive_web)
[CS IQC 65166-TG4-U000-50 ok.xlsx](https://drive.google.com/file/d/1P5tye3Yj6yb7kP9vuHH2vki9omq055pb/view?usp=drive_web)
Part No. : 65166-TG4-U000-50[35](https://drive.google.com/file/d/1P5tye3Yj6yb7kP9vuHH2vki9omq055pb/view?usp=drive_web)
[CS IQC63911-TG4R-T002-50 ok.xlsx](https://drive.google.com/file/d/1WyNh6q6wXxZGZoasXe9yyxVLvoQYql0c/view?usp=drive_web)
Part No. : 63911-TG4R-T002-50[36](https://drive.google.com/file/d/1WyNh6q6wXxZGZoasXe9yyxVLvoQYql0c/view?usp=drive_web)
[CS IQC 5301H197 ok.xlsx](https://drive.google.com/file/d/1xq0Z1qpdTFXEOpIjqvMpCrMj8sT4oKtK/view?usp=drive_web)
Part No. : 5301H197[37](https://drive.google.com/file/d/1xq0Z1qpdTFXEOpIjqvMpCrMj8sT4oKtK/view?usp=drive_web)
[CS IQC 5253AJ01,AJ02 ok.xlsx](https://drive.google.com/file/d/19pE_lQf70zRfVvT-84_Mf763mivcEkr_/view?usp=drive_web)
Part No. : 5253AJ01/5253AJ02[38](https://drive.google.com/file/d/19pE_lQf70zRfVvT-84_Mf763mivcEkr_/view?usp=drive_web)
[CS IQC 65167-TG2 -K000-H1.xlsx](https://drive.google.com/file/d/1IM4L1zNqGqQzv0jILIu-KBr5sQQESsbl/view?usp=drive_web)
Part No. : 65117-TG2-K000-H1[39](https://drive.google.com/file/d/1IM4L1zNqGqQzv0jILIu-KBr5sQQESsbl/view?usp=drive_web)
[CS IQC 5253AS80 ok.xlsx](https://drive.google.com/file/d/1uc-kdM-UaZEQiqSJT-hNekMhiKK8MaKX/view?usp=drive_web)
Part No. : 5253AS80[40](https://drive.google.com/file/d/1uc-kdM-UaZEQiqSJT-hNekMhiKK8MaKX/view?usp=drive_web)
[CS IQC 65702-TG2-K000-H1 ok.xlsx](https://drive.google.com/file/d/1lyGGiUTK-uGPheXY1-MkBQHDg4z4kLWT/view?usp=drive_web)
Part No. : 65702-TG2-K000-H1[41](https://drive.google.com/file/d/1lyGGiUTK-uGPheXY1-MkBQHDg4z4kLWT/view?usp=drive_web)
[CS IQC 5290D387 ok.xlsx](https://drive.google.com/file/d/1wctzCXvSnXp2nPpVRoD4A-C2ENmQeUge/view?usp=drive_web)
Part No. : 5290D387[42](https://drive.google.com/file/d/1wctzCXvSnXp2nPpVRoD4A-C2ENmQeUge/view?usp=drive_web)
[CS IQC 65142_TE7.xlsx](https://drive.google.com/file/d/1uyX7pmvGIP8OVxikR7QpL4_89ID97oqa/view?usp=drive_web)
Part No. : 65142-TE7-K000-H1[43](https://drive.google.com/file/d/1uyX7pmvGIP8OVxikR7QpL4_89ID97oqa/view?usp=drive_web)
[CS IQC 5313B275,276 ok.xlsx](https://drive.google.com/file/d/15PpuUYAzMfXRx1rq4vLZEjCgtK9RgnKW/view?usp=drive_web)
Part No. : 5313B275/ 5313B276[44](https://drive.google.com/file/d/15PpuUYAzMfXRx1rq4vLZEjCgtK9RgnKW/view?usp=drive_web)
[CS IQC 5230G083,084 ok.xlsx](https://drive.google.com/file/d/1s8VpvDrdjKyf_9SANaW6QaRi72aNbIbD/view?usp=drive_web)
Part No. : 65192-TG4R-T000[45](https://drive.google.com/file/d/1s8VpvDrdjKyf_9SANaW6QaRi72aNbIbD/view?usp=drive_web)
[CS IQC 5305A777,78ok.xlsx](https://drive.google.com/file/d/1TuRxVd18ZVEZWub6WiKmIxBUakyGdrIg/view?usp=drive_web)
Part No. : 5305A777/ 5305A778[46](https://drive.google.com/file/d/1TuRxVd18ZVEZWub6WiKmIxBUakyGdrIg/view?usp=drive_web)
[CS IQC 5313B269,270 ok.xlsx](https://drive.google.com/file/d/1r5TIKMfVnTA9pfUo80yawQpXBwIiHWwB/view?usp=drive_web)
Part No. : 5313B269/ 5313B270[47](https://drive.google.com/file/d/1r5TIKMfVnTA9pfUo80yawQpXBwIiHWwB/view?usp=drive_web)
[CS IQC 65799-TG4R-T001-H1.xlsx](https://drive.google.com/file/d/1Z7QL4VpUwlTCRvddzOSiiOerNe2n0rsc/view?usp=drive_web)
Part No. : 65799-TG4R-T001-H1[48](https://drive.google.com/file/d/1Z7QL4VpUwlTCRvddzOSiiOerNe2n0rsc/view?usp=drive_web)
[CS IQC 5290D389 ok.xlsx](https://drive.google.com/file/d/1dDJjLP77IrgczLrZ1s6Tpc8v0wDq5xdh/view?usp=drive_web)
Part No. : 5290D389[49](https://drive.google.com/file/d/1dDJjLP77IrgczLrZ1s6Tpc8v0wDq5xdh/view?usp=drive_web)
[CS IQC 62141_T0T.xlsx](https://drive.google.com/file/d/15wEQXxscEwICsGBMVxlRz_TT5T_ZChwf/view?usp=drive_web)
Part No. : 62141-T0T -H000-50[50](https://drive.google.com/file/d/15wEQXxscEwICsGBMVxlRz_TT5T_ZChwf/view?usp=drive_web)
[CS IQC 65701-TG1-T000-50.xlsx](https://drive.google.com/file/d/1npC44NSSoh53xcnjfYxQG89A8xtsQnRg/view?usp=drive_web)
Part No. : 65701-TG1-T000-50[51](https://drive.google.com/file/d/1npC44NSSoh53xcnjfYxQG89A8xtsQnRg/view?usp=drive_web)
[CS IQC 65716 -TG2 -K001-50.xlsx](https://drive.google.com/file/d/1WQ5A46gWx_4neLyHp-LolzrrBNkerIlg/view?usp=drive_web)
Part No. : 65716-TG2-K001-50[52](https://drive.google.com/file/d/1WQ5A46gWx_4neLyHp-LolzrrBNkerIlg/view?usp=drive_web)
[CS IQC 65741-TG4R-T001-H1.xlsx](https://drive.google.com/file/d/1q55qAlOJVmqSCHE7yTUsYP5iu5Nq5vDD/view?usp=drive_web)
Part No. : 65741-TG4R-T001-H1[53](https://drive.google.com/file/d/1q55qAlOJVmqSCHE7yTUsYP5iu5Nq5vDD/view?usp=drive_web)
[CS IQC 64221_T5L.xlsx](https://drive.google.com/file/d/10PhGpwC7_JAGRCG2K1m9-PuTDGEquRHQ/view?usp=drive_web)
Part No. : 64221-T5L -T000-50[54](https://drive.google.com/file/d/10PhGpwC7_JAGRCG2K1m9-PuTDGEquRHQ/view?usp=drive_web)
[CS IQC 64314-TG4R-T002-50.xlsx](https://drive.google.com/file/d/1BbG9N3dwzu3rVEesS7qqJR97O9viQ8__/view?usp=drive_web)
Part No. : 64314-TG4R-T002-50[55](https://drive.google.com/file/d/1BbG9N3dwzu3rVEesS7qqJR97O9viQ8__/view?usp=drive_web)
[CS IQC 5251D644 ok.xlsx](https://drive.google.com/file/d/1K_SpUM27e_diIKsx3p7O0Cvx9xFuq2-7/view?usp=drive_web)
Part No. : 5251D644[56](https://drive.google.com/file/d/1K_SpUM27e_diIKsx3p7O0Cvx9xFuq2-7/view?usp=drive_web)
[CS IQC 65793-TG1-T000-H1.xlsx](https://drive.google.com/file/d/13nu4Fsi4z-2FN_-MpSvjBELy5wLj7cUc/view?usp=drive_web)
Part No. : 65793-TG1-T000-H1[57](https://drive.google.com/file/d/13nu4Fsi4z-2FN_-MpSvjBELy5wLj7cUc/view?usp=drive_web)
[CS IQC 5253AL06,AU25 ok.xlsx](https://drive.google.com/file/d/1XlHAJESxnBd8e5rFAmqWsMgZimXhCavz/view?usp=drive_web)
Part No. : 5253AL06/5253AU25[58](https://drive.google.com/file/d/1XlHAJESxnBd8e5rFAmqWsMgZimXhCavz/view?usp=drive_web)
[CS IQC 5290D386 ok.xlsx](https://drive.google.com/file/d/1XdQFk868zLy4WzGsU18sBeBCg9Iw09yS/view?usp=drive_web)
Part No. : 5290D386[59](https://drive.google.com/file/d/1XdQFk868zLy4WzGsU18sBeBCg9Iw09yS/view?usp=drive_web)
[CS IQC 5253AU23,24 ok.xlsx](https://drive.google.com/file/d/1z-KUyCIqfNGpaXPFBi_v8UR59HrgSifn/view?usp=drive_web)
Part No. : 5253AU23 / 5253AU24[60](https://drive.google.com/file/d/1z-KUyCIqfNGpaXPFBi_v8UR59HrgSifn/view?usp=drive_web)
[CS IQC 5220L001,L092 ok.xlsx](https://drive.google.com/file/d/11btt1QOU06iU09JcM1hkle_u_F8cYAu2/view?usp=drive_web)
Part No. : 5220L001/ 5220L092[61](https://drive.google.com/file/d/11btt1QOU06iU09JcM1hkle_u_F8cYAu2/view?usp=drive_web)
[CS IQC 5253AJ78 ok.xlsx](https://drive.google.com/file/d/1ioX2odX3QTOUz5528AREgL1xIH-muyZM/view?usp=drive_web)
Part No. : 5253AJ78[62](https://drive.google.com/file/d/1ioX2odX3QTOUz5528AREgL1xIH-muyZM/view?usp=drive_web)
[CS IQC '63915_T5A.xlsx](https://drive.google.com/file/d/1jqqsUWuhwaAmtDDqDcZtl_3iOI-yXXyz/view?usp=drive_web)
Part No. : 63915-TSA -K000-50[63](https://drive.google.com/file/d/1jqqsUWuhwaAmtDDqDcZtl_3iOI-yXXyz/view?usp=drive_web)
[CS IQC 65192_TRDZ.xlsx](https://drive.google.com/file/d/1EhwxqmQUi7eJHWAbecSAkSoFO6-EtOue/view?usp=drive_web)
Part No. : 65192-TRDZ-P000-H1[64](https://drive.google.com/file/d/1EhwxqmQUi7eJHWAbecSAkSoFO6-EtOue/view?usp=drive_web)
[CS IQC 65168-TG2 -K000-H1.xlsx](https://drive.google.com/file/d/1mBw7in0x6kEuwEKOWTdmitpS5NNzlbfM/view?usp=drive_web)
Part No. : 65117-TG2-K000-H1[65](https://drive.google.com/file/d/1mBw7in0x6kEuwEKOWTdmitpS5NNzlbfM/view?usp=drive_web)
[CS IQC 62198_T8N.xlsx](https://drive.google.com/file/d/1qWZCKpORTinYJauu8T3LcHHuyC5_NHGm/view?usp=drive_web)
Part No. : 65536-3K6-K003-50-R[66](https://drive.google.com/file/d/1qWZCKpORTinYJauu8T3LcHHuyC5_NHGm/view?usp=drive_web)
[CS IQC 65711-TG4R-T001-50.xlsx](https://drive.google.com/file/d/19N2rbRHSSrD5mh76O50mw0BPwCMzmoXY/view?usp=drive_web)
Part No. : 65711-TG4R-T001-50[67](https://drive.google.com/file/d/19N2rbRHSSrD5mh76O50mw0BPwCMzmoXY/view?usp=drive_web)
[CS IQC 64311-TG4R-T002-H1 ok.xlsx](https://drive.google.com/file/d/16Bn3fhSoxokZsvnTNjOCD7-sQnrM2vlV/view?usp=drive_web)
Part No. : 64311-TG4R-T002-H1[68](https://drive.google.com/file/d/16Bn3fhSoxokZsvnTNjOCD7-sQnrM2vlV/view?usp=drive_web)
[CS IQC 62146_T0A.xlsx](https://drive.google.com/file/d/1Lqq-5evy3Uc1Xg0c0KhTsDO-K_yZYQPS/view?usp=drive_web)
Part No. : 62146-T0A -A000-H1[69](https://drive.google.com/file/d/1Lqq-5evy3Uc1Xg0c0KhTsDO-K_yZYQPS/view?usp=drive_web)
[CS IQC 65118_TG2.xlsx](https://drive.google.com/file/d/1l4RmeCBdSTEsx4gORn6bro8EPJ7NgyH3/view?usp=drive_web)
Part No. : 65118-TG2-K000-H1[70](https://drive.google.com/file/d/1l4RmeCBdSTEsx4gORn6bro8EPJ7NgyH3/view?usp=drive_web)
[CS IQC 5253AL19,20 ok.xlsx](https://drive.google.com/file/d/1daL_l34vqLmjfDj17IhLbPGaMAezP0Lz/view?usp=drive_web)
Part No. : 5253AL19 / 5253AL20[71](https://drive.google.com/file/d/1daL_l34vqLmjfDj17IhLbPGaMAezP0Lz/view?usp=drive_web)
[CS IQC 5290D384 ok.xlsx](https://drive.google.com/file/d/1QNTBEP1uesliYxkYm55BlDkSClRKqS2o/view?usp=drive_web)
Part No. : 5290D384[72](https://drive.google.com/file/d/1QNTBEP1uesliYxkYm55BlDkSClRKqS2o/view?usp=drive_web)
[CS IQC 5290D383 ok.xlsx](https://drive.google.com/file/d/1GOppykZwUNuBv8a22zUR80pe_-J0rz0s/view?usp=drive_web)
Part No. : 5290D383[73](https://drive.google.com/file/d/1GOppykZwUNuBv8a22zUR80pe_-J0rz0s/view?usp=drive_web)
[CS IQC 65168_TG2.xlsx](https://drive.google.com/file/d/1_TRZpOTQ8WS9yQwcaHJFAShdYqr2TmS2/view?usp=drive_web)
Part No. : 65168-TG2-K000-H1[74](https://drive.google.com/file/d/1_TRZpOTQ8WS9yQwcaHJFAShdYqr2TmS2/view?usp=drive_web)
[CS IQC 62143_T0A.xlsx](https://drive.google.com/file/d/1MPGVb7O2W01SPcE5CqO8WKG15q8IBkDt/view?usp=drive_web)
Part No. : 62143-T0A -A000-50[75](https://drive.google.com/file/d/1MPGVb7O2W01SPcE5CqO8WKG15q8IBkDt/view?usp=drive_web)
[CS IQC 17522-TG4.xlsx](https://drive.google.com/file/d/1j2S62uVAADl_caKR6P2xQDvBdFJ_CFyZ/view?usp=drive_web)
Part No. : 17522-TG4 -T000-21[76](https://drive.google.com/file/d/1j2S62uVAADl_caKR6P2xQDvBdFJ_CFyZ/view?usp=drive_web)
[CS IQC 65118-TG2-K000-H1.xlsx](https://drive.google.com/file/d/1woJPsmXT57HhwRAa74vGWpJMLa9ECnsm/view?usp=drive_web)
Part No. : 65117-TG2-K000-H1[77](https://drive.google.com/file/d/1woJPsmXT57HhwRAa74vGWpJMLa9ECnsm/view?usp=drive_web)
[CS IQC 5253AS77 ok.xlsx](https://drive.google.com/file/d/1C1qRN30eHouIW_spCKigG1megMakkwmp/view?usp=drive_web)
Part No. : 5253AS77 / 5253AS78[78](https://drive.google.com/file/d/1C1qRN30eHouIW_spCKigG1megMakkwmp/view?usp=drive_web)
[735D912D.tmp](https://drive.google.com/file/d/18zbghHUNn5_IzTsZsd005kN6du7UDZUv/view?usp=drive_web)
Part No. : 17528-T5S -T000-H1[79](https://drive.google.com/file/d/18zbghHUNn5_IzTsZsd005kN6du7UDZUv/view?usp=drive_web)
[CS IQC 65743-TG1-T000-H1.xlsx](https://drive.google.com/file/d/1dA7ZXOuY3oB6jv2i799eFpAnxmyZ971q/view?usp=drive_web)
Part No. : 65743-TG1-T000-H1[80](https://drive.google.com/file/d/1dA7ZXOuY3oB6jv2i799eFpAnxmyZ971q/view?usp=drive_web)
[CS IQC 62144_T0T.xlsx](https://drive.google.com/file/d/1wqWqyErCP3o4fWP3amRryPqp7oGAaQeu/view?usp=drive_web)
Part No. : 62144-T0T -H002-H1[81](https://drive.google.com/file/d/1wqWqyErCP3o4fWP3amRryPqp7oGAaQeu/view?usp=drive_web)
[CS IQC 4140A487 ok.xlsx](https://drive.google.com/file/d/1s9HW2BFSBE0Ctx_Qf09Ua1ZyHpXja4HA/view?usp=drive_web)
Part No. : 4140A487[82](https://drive.google.com/file/d/1s9HW2BFSBE0Ctx_Qf09Ua1ZyHpXja4HA/view?usp=drive_web)
[CS IQC 5220K867 ok.xlsx](https://drive.google.com/file/d/1C1A86knUI0eENWdUjvC5QFpjfq5YJI5I/view?usp=drive_web)
Part No. : 5220K867[83](https://drive.google.com/file/d/1C1A86knUI0eENWdUjvC5QFpjfq5YJI5I/view?usp=drive_web)
[CS IQC 5314A801,802 ok.xlsx](https://drive.google.com/file/d/1vnmzAPGkX7I6E6HDZVsIsQKPY6qKM0xi/view?usp=drive_web)
Part No. : 5314A801/ 5314A802[84](https://drive.google.com/file/d/1vnmzAPGkX7I6E6HDZVsIsQKPY6qKM0xi/view?usp=drive_web)
[CS IQC 5220K988, 989ok.xlsx](https://drive.google.com/file/d/1NrCGwSHUYnDU72y0_qP5K5OSvU2IZ43c/view?usp=drive_web)
Part No. : 5220K988/5220K989[85](https://drive.google.com/file/d/1NrCGwSHUYnDU72y0_qP5K5OSvU2IZ43c/view?usp=drive_web)
[CS IQC 5253AU26,AL32 ok.xlsx](https://drive.google.com/file/d/1cz4eRkthk1yy98AhZmws8MKfd_347mrO/view?usp=drive_web)
Part No. : 5253AU26 / 5253AL39[86](https://drive.google.com/file/d/1cz4eRkthk1yy98AhZmws8MKfd_347mrO/view?usp=drive_web)
[CS IQC 5253AN87,88ok.xlsx](https://drive.google.com/file/d/1Cco-eyUrMUcwOrR_RJQPMjDUj1ZKc76u/view?usp=drive_web)
Part No. : 5253AN87/ 5253AN88[87](https://drive.google.com/file/d/1Cco-eyUrMUcwOrR_RJQPMjDUj1ZKc76u/view?usp=drive_web)
[CS IQC 62198_T5L.xlsx](https://drive.google.com/file/d/148ZLw6mIMKMxfdsF23PtNUr9r8LBkX89/view?usp=drive_web)
Part No. : 62198-T5L -T000-H1[88](https://drive.google.com/file/d/148ZLw6mIMKMxfdsF23PtNUr9r8LBkX89/view?usp=drive_web)
[CS IQC 65742-TG4R-T001-H1.xlsx](https://drive.google.com/file/d/1GM55bpd0ZewOVMS9I3ZDsgNjjd_QUnbL/view?usp=drive_web)
Part No. : 65742-TG4R-T000-H1[89](https://drive.google.com/file/d/1GM55bpd0ZewOVMS9I3ZDsgNjjd_QUnbL/view?usp=drive_web)
"""

def clean_pn(val: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', val or '').upper()

async def execute_cancellation():
    prompt_items = []
    current_file = ''
    for line in USER_RAW_TEXT.strip().split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('['):
            current_file = line
        elif 'Part No.' in line:
            pm = re.search(r'Part No\.\s*:\s*([^\[]+)', line)
            if pm:
                pns = [p.strip() for p in re.split(r'[/,]', pm.group(1)) if p.strip()]
                prompt_items.append({'file': current_file, 'pns': pns})

    prompt_clean_pns = set()
    for item in prompt_items:
        for p in item['pns']:
            c = clean_pn(p)
            if c: prompt_clean_pns.add(c)

    prompt_filenames = set()
    for item in prompt_items:
        fm = re.match(r'\[([^\]]+)\]', item['file'])
        if fm:
            prompt_filenames.add(fm.group(1).lower().strip())

    async with AsyncSessionLocal() as session:
        all_cs = (await session.scalars(select(Checksheet))).all()
        pts = (await session.scalars(select(InspectionPoint))).all()
        pts_by_cs = defaultdict(list)
        for p in pts:
            pts_by_cs[p.checksheet_id].append(p)

        target_checksheets = {}

        for cs in all_cs:
            rfp = (cs.raw_file_path or '').replace('\\\\', '/').lower()
            fname = rfp.split('/')[-1] if '/' in rfp else rfp
            cpn = clean_pn(cs.clean_part_number or cs.part_number)

            reasons = []

            # 1. Material Incoming folders / Coil / Blank / Sheet
            if any(k in rfp for k in [
                'material incoming',
                'material  incoming',
                'iqc material',
                'iqc coil',
                'iqc sheet',
                'blank'
            ]):
                reasons.append("Folder Material Incoming / Coil / Blank")

            # 2. Filename match with prompt
            if any(pf in fname or fname in pf for pf in prompt_filenames):
                reasons.append("Prompt Filename Match")

            # 3. Part number match with prompt
            for tp in prompt_clean_pns:
                if cpn == tp or (len(tp) >= 10 and cpn.startswith(tp[:10])):
                    reasons.append(f"Prompt Part No Match ({tp})")
                    break

            # 4. Inspection point has Millsheet + Coil / Gulungan standard
            cs_pts = pts_by_cs.get(cs.id, [])
            if any('millsheet' in (p.method or '').lower() for p in cs_pts) and any('coil' in (p.standard or '').lower() or 'gulungan' in (p.standard or '').lower() for p in cs_pts):
                reasons.append("Inspection Spec: Millsheet + Coil")

            if reasons:
                target_checksheets[cs.id] = {
                    "cs": cs,
                    "reasons": reasons
                }

        print(f"Total checksheets to cancel: {len(target_checksheets)}")

        # Collect FactoryHub checksheets
        with_fh = []
        status_prev_counts = defaultdict(int)

        for cs_id, data in target_checksheets.items():
            cs = data["cs"]
            status_prev_counts[cs.status] += 1
            if cs.factoryhub_url:
                with_fh.append(cs)

            # Update checksheet record
            cs.status = "Canceled"
            cs.keterangan = "Part Incoming Material / IQC Coil & Plat (Dibatalkan)"
            cs.updated_at = datetime.utcnow()

        # Log activity
        log = ActivityLog(
            action="BATCH_CANCEL_INCOMING",
            operator="Zul (AI Assistant)",
            status="SUCCESS",
            details=f"Dibatalkan {len(target_checksheets)} part incoming material (Coil/Plat/Millsheet) & 89 list Gemini. {len(with_fh)} part tercatat di FactoryHub untuk dihapus."
        )
        session.add(log)

        await session.commit()
        print("Successfully committed changes to database!")

        # Print statistics
        print("\nPrevious Status Breakdown of Canceled Checksheets:")
        for st, cnt in sorted(status_prev_counts.items()):
            print(f"  {st:20s}: {cnt}")

        print(f"\nTotal checksheets on FactoryHub to delete: {len(with_fh)}")

        # Export list of FactoryHub checksheets to CSV / TXT artifact
        export_path = "/Users/mac/Developer/Summit/Otomatisasi Checksheet/data/factoryhub_to_delete.txt"
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            f.write("=== DAFTAR PART INCOMING MATERIAL / COIL UNTUK DIHAPUS DI FACTORYHUB ===\n")
            f.write(f"Total Part di FactoryHub: {len(with_fh)}\n")
            f.write(f"Tanggal: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"{'No':<4} | {'CS ID':<6} | {'Customer':<12} | {'Part Number':<24} | {'Part Name':<30} | {'FactoryHub URL'}\n")
            f.write("-" * 120 + "\n")
            for idx, cs in enumerate(sorted(with_fh, key=lambda x: (x.customer or '', x.part_number or '')), 1):
                f.write(f"{idx:<4} | {cs.id:<6} | {(cs.customer or '-'):<12} | {(cs.part_number or '-'):<24} | {(cs.part_name or '-'):<30} | {cs.factoryhub_url}\n")

        print(f"Saved FactoryHub deletion list to: {export_path}")

        # Invalidate cache if possible
        try:
            from services.cache_service import invalidate_checksheets_cache
            invalidate_checksheets_cache()
            print("Checksheet cache invalidated successfully.")
        except Exception as e:
            print(f"Cache invalidation note: {e}")

if __name__ == "__main__":
    asyncio.run(execute_cancellation())
