
class DummyClient:
    def get_filter_years(self):
        return [2024, 2025, 2026]

    def get_filter_products(self):
        return ["Phone", "Tab", "PC", "Monitor"]

    def list_projects(self, year=None, product=None):
        """Simulates API call for fetching projects with filters."""
        params = {}
        if year: params['year'] = year
        if product: params['product'] = product

        # 해당 params를 가지고 서버에 요청을 보냄
        # In production: response = requests.get(f"{BASE_URL}/projects", params={'year': year, ...})
        # return response.json()
        return [{'_cell_marker': 'SDC', '_date_dvr': '2023-11-30T00:00:00', '_date_pia': '2023-11-29T00:00:00', '_date_pra': '2023-11-30T00:00:00', '_date_pvr': '2023-11-30T00:00:00', '_date_sra': '2023-11-30T00:00:00', '_is_drop': '0', '_is_reuse': '0', '_model_name': 'test ankur 28-11-2023 1', 'classification': '구조', 'created_on': '2023-11-28T03:19:57', 'current_state@aras.name': 'Open', 'description': 'test project', 'generation': 1, 'id': 'B59F3CB971E74989A79516C1EB375209', 'indexed_on': '2023-11-30T09:06:13', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000007', 'keyed_name': '2023 test ankur 28-11-2023 1', 'major_rev': 'A', 'modified_on': '2023-11-28T03:21:20', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2023', 'name': 'test ankur 28-11-2023 1', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_cell_marker': 'SDP', '_date_pia': '2023-11-24T00:00:00', '_is_drop': '0', '_is_reuse': '0', '_model_name': '[ankur] testing project 11/30/2023 -1', 'classification': '구조', 'created_on': '2023-11-30T06:38:28', 'current_state@aras.name': 'Close', 'description': 'test project', 'generation': 1, 'id': 'A890896CA42F4737B067B8DBC68E0449', 'indexed_on': '2023-11-30T09:06:13', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000008', 'keyed_name': '2023 [ankur] testing project 11/30/2023 -1-1', 'major_rev': 'A', 'modified_on': '2023-11-30T06:47:18', 'new_version': '1', 'not_lockable': '0', 'state': 'Closed', '_development_year': '2023', 'name': '[ankur] testing project 11/30/2023 -1-1', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_cell_marker': 'SDC', '_date_dvr': '2023-12-22T00:00:00', '_date_pia': '2023-12-22T00:00:00', '_date_pra': '2023-12-27T00:00:00', '_date_pvr': '2023-12-30T00:00:00', '_date_sra': '2024-02-16T00:00:00', '_is_drop': '0', '_is_reuse': '0', 'classification': '구조', 'created_on': '2023-12-06T20:13:32', 'current_state@aras.name': 'Open', 'description': 'test project', 'generation': 1, 'id': '1B73E9EBEB0D45608CD66B15D2586142', 'indexed_on': '2023-12-06T20:32:47', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000009', 'keyed_name': '2023 [ankur] testing project 12-7-2023 - 1', 'major_rev': 'A', 'modified_on': '2023-12-06T20:13:32', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2023', 'name': '[ankur] testing project 12-7-2023 - 1', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_development_stage': 'Pre', '_is_drop': '0', '_is_reuse': '0', '_launch_region': '북미', '_model_name': 'Manual Test 1 -> 29 Jan 2024', '_product_category': 'TV', 'classification': '구조', 'created_on': '2024-01-29T04:46:05', 'current_state@aras.name': 'Open', 'generation': 1, 'id': 'FB36D15610AF44E7A9457876D9915EA0', 'indexed_on': '2024-01-29T05:28:12', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000010', 'keyed_name': '2024 Manual Test 1 -> 29 Jan 2024', 'major_rev': 'A', 'modified_on': '2024-01-29T04:46:05', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2024', 'name': 'Manual Test 1 -> 29 Jan 2024', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_is_drop': '0', '_is_reuse': '0', '_launch_region': '한국', '_model_name': 'Automation Testing 07 February 2024 14:53:11', '_product_category': 'Sound Device', 'classification': '구조', 'created_on': '2024-02-07T04:23:16', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '2D21FBF6CF8841AE907826ABC71DDBCA', 'indexed_on': '2024-02-07T04:31:26', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000011', 'keyed_name': '2024 Automation Testing 07 February 2024 14:53:11', 'major_rev': 'A', 'modified_on': '2024-02-07T04:23:16', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2024', 'name': 'Automation Testing 07 February 2024 14:53:11', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_is_drop': '1', '_is_reuse': '0', '_launch_region': '중남미', '_model_name': 'Manual Test 1 -> 23 Jan 2024', '_product_category': 'TV', 'classification': '구조', 'created_on': '2024-10-01T11:04:50', 'current_state@aras.name': 'Close', 'description': 'dfefferferf', 'generation': 1, 'id': '2ED99263EE82421D858926E095380C8E', 'indexed_on': '2026-01-02T01:53:44', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000015', 'keyed_name': '2024 선행 과제 1', 'major_rev': 'A', 'modified_on': '2026-01-02T01:19:43', 'new_version': '1', 'not_lockable': '0', 'state': 'Close', '_development_year': '2024', 'name': '선행 과제 1', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_is_drop': '0', '_is_reuse': '0', '_launch_region': '북미', '_model_name': 'manual testing', '_product_category': 'TV', 'classification': '구조', 'created_on': '2024-10-03T01:01:11', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '8D624384B16C4E8D9D174C48E85D5C42', 'indexed_on': '2024-11-06T16:17:25', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000016', 'keyed_name': '2024 manual test 03 -oct 24 1', 'major_rev': 'A', 'modified_on': '2024-10-03T01:01:11', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2024', 'name': 'manual test 03 -oct 24 1', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_cell_marker': 'SDC', '_is_drop': '0', '_is_reuse': '0', '_launch_region': '북미,중남미', '_model_name': 'test', '_product_category': 'TV', 'classification': '구조', 'created_on': '2025-09-01T00:41:44', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '923B53A689F842BB837668258112B207', 'indexed_on': '2026-02-02T02:56:32', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000017', 'keyed_name': '2025 test project', 'major_rev': 'A', 'modified_on': '2026-02-02T02:48:20', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2025', 'name': 'test project', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_cell_marker': 'BOE,SDP', '_date_pia': '2025-12-25T00:00:00', '_development_stage': 'Pre', '_is_drop': '1', '_is_reuse': '0', '_launch_region': '북미', '_model_name': 'Hotel Model', '_product_category': 'HotelTV', 'classification': '구조', 'created_on': '2025-09-22T03:18:24', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '8844589D70FA4B259795B506C9487069', 'indexed_on': '2026-01-02T01:53:44', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000018', 'keyed_name': '2025 TV XVZ', 'major_rev': 'A', 'modified_on': '2026-01-02T01:19:10', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2025', 'name': 'TV XVZ', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_cell_marker': 'AUO,BOE', '_development_stage': 'Pre', '_is_drop': '0', '_is_reuse': '0', '_launch_region': '북미', '_model_name': 'TV ABC', '_product_category': 'HotelTV', 'classification': '구조', 'created_on': '2025-09-22T04:55:22', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '4F30EE766AC64AE5AD1C59009FC65FF9', 'indexed_on': '2026-01-02T01:53:44', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000019', 'keyed_name': '2025 Product XVZ', 'major_rev': 'A', 'modified_on': '2026-01-02T01:29:04', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2025', 'name': 'Product XVZ', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_is_drop': '0', '_is_reuse': '0', 'classification': '회로', 'created_on': '2026-01-22T01:07:42', 'current_state@aras.name': 'Open', 'generation': 1, 'id': 'B96181E175D6422597DFF9E46A1F361A', 'indexed_on': '2026-01-22T01:50:42', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000020', 'keyed_name': '2025 Test', 'major_rev': 'A', 'modified_on': '2026-01-22T01:07:47', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2025', 'name': 'Test', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}, {'_is_drop': '0', '_is_reuse': '0', '_model_name': 'ABC', '_product_category': 'TV', 'classification': '구조', 'created_on': '2026-02-02T02:46:47', 'current_state@aras.name': 'Open', 'generation': 1, 'id': '2C1983C25A1E427BB2775994F9A7A9A4', 'indexed_on': '2026-02-02T02:56:32', 'is_current': '1', 'is_released': '0', 'item_number': 'PROJ-000021', 'keyed_name': '2026 2026 ABC TV', 'major_rev': 'A', 'modified_on': '2026-02-02T02:47:07', 'new_version': '1', 'not_lockable': '0', 'state': 'Open', '_development_year': '2026', 'name': '2026 ABC TV', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}]

    def list_sim_requests(self, project_id):
        """Simulates fetching Simulation Requests (SR) for a project."""
        return [{'_background': 'test', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000044', '_objective': 'test', '_project_dev_year': '2025', '_simulation_type': '세트 강성 강도 시뮬레이션', '_target_date': '2025-09-15T13:42:37', 'classification': '구조', 'created_on': '2025-09-01T00:42:53', 'current_state@aras.name': 'In Work', 'generation': 1, 'id': '775A49135F07482AB1E75717B8D2C832', 'indexed_on': '2025-11-26T05:57:29', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000044 세트 강성 강도 시뮬레이션', 'major_rev': 'A', 'modified_on': '2025-11-26T05:54:55', 'new_version': '1', 'not_lockable': '0', 'state': 'In Work', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}, {'_background': 'Product sale', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000045', '_objective': 'Support cost evaluation ', '_project_dev_year': '2025', '_request_type': '발주 전 설계 검토', '_request_type_input': '발주 전 설계 검토', '_simulation_type': '열 유동 시뮬레이션', '_target_date': '2025-10-06T14:15:48', 'classification': '구조', 'created_on': '2025-09-22T04:47:20', 'current_state@aras.name': 'In Review', 'generation': 1, 'id': 'CFD88F34C1B54BCF8E07DC7D3BF2939E', 'indexed_on': '2025-09-22T05:36:49', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000045 32 TV', 'major_rev': 'A', 'modified_on': '2025-09-22T05:14:11', 'new_version': '1', 'not_lockable': '0', 'state': 'In Review', '_name': '32 TV', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}, {'_background': 'Build product for Hotel', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000046', '_objective': 'Cost evaluation', '_project_dev_year': '2025', '_request_type': '발주 전 설계 검토', '_request_type_input': '발주 전 설계 검토', '_simulation_type': '열 유동 시뮬레이션', '_target_date': '2025-10-06T14:27:30', 'classification': '구조', 'created_on': '2025-09-22T04:58:12', 'current_state@aras.name': 'Accepted', 'generation': 1, 'id': 'B5ECE840FB2E41BD92FCDDDA9B935C34', 'indexed_on': '2025-09-22T05:36:49', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000046 32 TV', 'major_rev': 'A', 'modified_on': '2025-09-22T04:59:22', 'new_version': '1', 'not_lockable': '0', 'state': 'Accepted', '_name': '32 TV', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}, {'_background': 'Product for hotel', '_date_lcm_mold_order': '2025-09-26T00:00:00', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000047', '_objective': 'Cost Evaulation', '_project_dev_year': '2025', '_request_type': '발주 전 설계 검토', '_request_type_input': '발주 전 설계 검토', '_simulation_type': '열 유동 시뮬레이션', '_target_date': '2025-12-25T00:00:00', 'classification': '구조', 'created_on': '2025-09-22T05:26:31', 'current_state@aras.name': 'New', 'generation': 1, 'id': '5C26698050FE4188A58759F250743CD2', 'indexed_on': '2025-09-22T05:36:49', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000047 32 TV', 'major_rev': 'A', 'modified_on': '2025-09-22T05:26:31', 'new_version': '1', 'not_lockable': '0', 'state': 'New', '_name': '32 TV', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}, {'_background': 'Product for hotel', '_date_lcm_mold_order': '2025-11-12T00:00:00', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000048', '_objective': 'Cost Evaluation', '_project_dev_year': '2025', '_request_type': '발주 전 설계 검토', '_request_type_input': '발주 전 설계 검토', '_simulation_type': '열 유동 시뮬레이션', '_target_date': '2025-12-27T00:00:00', 'classification': '구조', 'created_on': '2025-09-22T05:28:20', 'current_state@aras.name': 'In Work', 'generation': 1, 'id': 'F227F37A491A45239AEFD4EBA0B5E9E4', 'indexed_on': '2025-09-22T07:36:17', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000048 32 TV', 'major_rev': 'A', 'modified_on': '2025-09-22T06:48:25', 'new_version': '1', 'not_lockable': '0', 'state': 'In Work', '_name': '32 TV', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}, {'_background': 'Product for hotel', '_copied_from_id': 'F227F37A491A45239AEFD4EBA0B5E9E4', '_date_lcm_mold_order': '2025-11-12T00:00:00', '_development_stage': 'Pre', '_development_year': '2025', '_is_director_order': '0', '_item_number': 'SR-00000049', '_objective': 'Cost Evaluation', '_project_dev_year': '2025', '_request_type': '발주 전 설계 검토', '_request_type_input': '발주 전 설계 검토', '_simulation_type': '열 유동 시 뮬레이션', '_target_date': '2025-10-06T20:09:26', 'classification': '구조', 'created_on': '2025-09-22T07:09:26', 'current_state@aras.name': 'New', 'generation': 1, 'id': '08E851A3CCF84DF68BDFCF776092B1C9', 'indexed_on': '2025-09-22T07:36:17', 'is_current': '1', 'is_released': '0', 'keyed_name': 'SR-00000049 32 TV', 'major_rev': 'A', 'modified_on': '2025-09-22T07:09:30', 'new_version': '1', 'not_lockable': '0', 'state': 'New', '_name': '32 TV', 'itemtype': 'B40773BF94F644218B555A22B3BFDE08'}]


    # def list_work_requests(self, sr_id):
    #     """Simulates fetching Work Requests (WR) for an SR."""
        # json_string = """
        # {
        #     "inputs": [
        #         {"name": "PDN Impedance Analysis design Signal Integrity Check TDR + SIWave Batch.siw", "size": 122.3, "type": "siw"},
        #         {"name": "ports.json", "size": 0.4, "type": "json"}
        #     ],
        #     "outputs": [
        #         {"name": "result.s2p", "size": 18.1, "type": "s2p"},
        #         {"name": "chart.png", "size": 2.2, "type": "png"}
        #     ]
        # }
        # """
        # return json.loads(json_string)

    def list_work_requests_by_sr_id(self, sr_id):
        """Simulates fetching Work Requests (WR) for an SR."""
        return [
    {
        "_simulation_type":"세트 강성 강도 시뮬레이션",
        "classification":"구조",
        "created_on":"2025-09-01T00:54:30",
        "current_state@aras.name":"In Work",
        "date_finish_requested":"2025-09-15T13:42:37",
        "date_finish_scheduled":"2025-09-06T11:00:00",
        "date_start_actual":"2025-09-01T00:55:02",
        "generation":1,
        "id":"B9A7DE201C714BBA9BDC37474479CFA0",
        "indexed_on":"2025-10-29T06:41:08",
        "is_current":"1",
        "is_released":"0",
        "keyed_name":"WR-00000076 FE 모델링",
        "major_rev":"A",
        "modified_on":"2025-10-29T06:13:29",
        "new_version":"1",
        "not_lockable":"0",
        "state":"In Work",
        "item_number":"WR-00000076",
        "name":"FE 모델링",
        "itemtype":"4AE047D8E67A4FD59DB03CD74D64C430"
    },
    {
        "_simulation_type":"세트 강성 강도 시뮬레이션",
        "classification":"구조",
        "created_on":"2025-09-01T00:54:33",
        "current_state@aras.name":"New",
        "date_finish_requested":"2025-09-15T13:42:37",
        "generation":1,
        "id":"5AAD3AF05A4447C0B635E4022E0B6875",
        "indexed_on":"2025-09-16T12:19:19",
        "is_current":"1",
        "is_released":"0",
        "keyed_name":"WR-00000077 내충격 강성/강도",
        "major_rev":"A",
        "modified_on":"2025-09-01T00:54:34",
        "new_version":"1",
        "not_lockable":"0",
        "state":"New",
        "item_number":"WR-00000077",
        "name":"내충격 강성/강도",
        "itemtype":"4AE047D8E67A4FD59DB03CD74D64C430"
    },
    {
        "_simulation_type":"세트 강성 강도 시뮬레이션",
        "classification":"구조",
        "created_on":"2025-09-01T00:54:34",
        "current_state@aras.name":"New",
        "date_finish_requested":"2025-09-15T13:42:37",
        "generation":1,
        "id":"74C8C22922EF4F9E9514BB10E3A67A2B",
        "indexed_on":"2025-09-16T12:19:19",
        "is_current":"1",
        "is_released":"0",
        "keyed_name":"WR-00000078 배면 강성/강도",
        "major_rev":"A",
        "modified_on":"2025-09-01T00:54:34",
        "new_version":"1",
        "not_lockable":"0",
        "state":"New",
        "item_number":"WR-00000078",
        "name":"배면 강성/강도",
        "itemtype":"4AE047D8E67A4FD59DB03CD74D64C430"
    },
    {
        "_guide_image":"vault:///?fileId=A0F45BEED8A642519EA066CB558FA092",
        "_simulation_type":"세트 강성 강도 시뮬레이션",
        "classification":"구조",
        "created_on":"2025-11-26T05:54:49",
        "current_state@aras.name":"New",
        "date_finish_requested":"2025-09-15T13:42:37",
        "flow_meta":"[{\"id\":\"B78A1BE11BEC430BA9F4065493DC521F\",\"position\":{\"x\":100.0,\"y\":200.0}},{\"id\":\"84A9A2C8F9944045A31CB1120A2F3272\",\"position\":{\"x\":1000.0,\"y\":200.0}}]",
        "generation":1,
        "id":"54AC0D85C8F44769BA6D3B26E9FC4093",
        "indexed_on":"2025-11-26T05:56:57",
        "is_current":"1",
        "is_released":"0",
        "keyed_name":"WR-00000085 스탠드 리프트 강성/강도",
        "major_rev":"A",
        "modified_on":"2025-11-26T05:54:50",
        "new_version":"1",
        "not_lockable":"0",
        "state":"New",
        "item_number":"WR-00000085",
        "name":"스탠드 리프트 강성/강도",
        "itemtype":"4AE047D8E67A4FD59DB03CD74D64C430"
    }
    ]

    def list_work_request_files(self, wr_id):
        """Simulates fetching file list for a specific WR."""
        return {
            "Input":[
                {
                    "id":"C9FD71B09E3B4DCA8B36784E0A8FFD2A",
                    "name":"Model.log",
                    "size":"8259",
                    "is_folder":False,
                    "file_id":"None",
                    "type":"File/Other/Other"
                },
                {
                    "id":"E539AAF704E1428FA6C5C5DBCACF4523",
                    "name":"test.brd",
                    "size":"59810",
                    "is_folder":False,
                    "file_id":"None",
                    "type":"File/CAD/Other"
                }
            ],
            "Output":[
                {
                    "id":"C9E711A14F3644EA8715763F217BBB3C",
                    "name":"folder1",
                    "size":"None",
                    "is_folder":True,
                    "file_id":"None",
                    "type":"Folder"
                },
                {
                    "id":"D32764AF7686426482DA4E94D976BCF3",
                    "name":"folder2",
                    "size":"None",
                    "is_folder":True,
                    "file_id":"None",
                    "type":"Folder"
                },
                {
                    "id":"2AAC9DC0C47B46B4BAF016C871AB1A9A",
                    "name":"test.brd",
                    "size":"59810",
                    "is_folder":False,
                    "file_id":"None",
                    "type":"File/CAD/Other"
                }
            ]
            }

    def get_project_by_id(self, project_id):
        return {'created_on': '2026-01-22T03:35:06', 'generation': 1, 'id': 'D5FAA558496E44A187863D21CCA371AC', 'is_current': '1', 'is_released': '0', 'keyed_name': 'PROJ-000001', 'major_rev': 'A', 'modified_on': '2026-01-22T03:35:06', 'name': 'FirstProject', 'new_version': '1', 'not_lockable': '0', 'item_number': 'PROJ-000001', 'itemtype': '7A64896F98564F1E8F1C9D1C91C56515'}
