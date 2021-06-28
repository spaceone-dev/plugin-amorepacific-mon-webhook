import re
import logging
import hashlib
from spaceone.core import utils
from spaceone.core.manager import BaseManager
from datetime import datetime
from spaceone.monitoring.model.event_response_model import EventModel

_LOGGER = logging.getLogger(__name__)

TITLE_PARSING_META = [' - ']
_TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%S'


class EventManager(BaseManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def parse(self, options, raw_data):
        """
                "event_time": "2021-06-27 02:20:50",
                "host_ip": "apne1-insfrprd-ecp-ecprds.cfqdcjczxddr.ap-northeast-1.rds.amazonaws.com",
                "summary": "07. DB그룹>10.INNISFREE GLOBAL>PostgreSQL 10 (apne1-insfrprd-ecp-ecprds.cfqdcjczxddr.ap-northeast-1.rds.amazonaws.com : INSFRPRDDB)>Databases>INSFRPRDDB",
                "event_id": "32326983",
                "status": "UP ",
                "urgency": "1",
                "metric_value": "Rollback 수 [주의 > 0 Count/s, 해제 = 0 Count/s] ",
                "severity": "주의",
                "threshold": "INSFRPRDDB",
                "conditionlog": "Rollback 수 [0.02 Count/s (> 0 Count/s)]",
                "metric_name": "롤백 발생 "


                "metric_value": "이벤트 탐지 [심각도: ERROR , 개행 포함, 내용 패턴: (?=.*member.*)(^((?!MLEC_MEMBER_NOT_FOUND).)*$)] ",
                "summary": "01. APMALL>EAPWAS-172.28.103.146>monitor group>ecp-api.log_member",
                "threshold": "ecp-api.log_member",
                "event_time": "2021-06-27 02:17:10",
                "status": "UP ",
                "conditionlog": "[1회 발생] 이벤트 탐지 [심각도: ERROR, 내용: [2021-06-27 02:17:08,176] [ERROR] [ http-nio-8080-exec-5] [B2CMON_LOG.logging:124] [MON|2021-06-27 02:17:08,176|ERROR|M01||MobileWeb|member||||MLEC_MEMBER_AUTH_FAILURE|/MON] Fail. API=post:/v1/M01/ap/members/joinOnLogin, resultMsg=Authentication Failure [MemberUtils.memberMonLoggingError:457 < ApMemberAuthRestApi.login:318 < ApMemberAuthRestApi.joinOnLogin:415 < GeneratedMethodAccessor4391.invoke:-1 < DelegatingMethodAccessorImpl.invoke:43]]",
                "host_ip": "172.28.103.146",
                "metric_name": "회원_경고로그 ",
                "severity": "경고",
                "resource_name": "EAPWAS-172.28.103.146",
                "urgency": "2",
                "event_id": "32326947"

        """
        default_parsed_data_list = []

        event_key = raw_data.get('event_id')
        ip_address = raw_data.get('host_ip')
        resource_id = raw_data.get('resource_name')
        metric_name = raw_data.get('metric_name').strip() if isinstance(raw_data.get('metric_name'), str) else ''
        metric_value = raw_data.get('metric_value').strip() if isinstance(raw_data.get('metric_value'), str) else ''
        event_resource_vo = {}

        try:

            # if ip_address is not None:
            #     event_resource_vo.update({'ip_address': ip_address})

            if resource_id is not None:
                event_resource_vo.update({'resource_id': resource_id})
                event_resource_vo.update({'name': f'{resource_id}'})

            parsed_summary = self._parse_summary(raw_data)

            event_vo = {
                'event_key': event_key,
                'event_type': 'ALERT',
                'severity': 'CRITICAL',
                'resource': event_resource_vo,
                'description': parsed_summary.get('body'),
                'title': parsed_summary.get('title'),
                'rule': f'{metric_name}: {metric_value}',
                'occurred_at': self._occurred_at(raw_data),
                'additional_info': {}
            }

            _LOGGER.debug(f'[EventManager] parse Event : {event_vo}')

            event_result_model = EventModel(event_vo, strict=False)
            event_result_model.validate()
            event_result_model_native = event_result_model.to_native()
            default_parsed_data_list.append(event_result_model_native)

        except Exception as e:
            generated = utils.generate_id('amore-pacific', 4)
            hash_object = hashlib.md5(generated.encode())
            md5_hash = hash_object.hexdigest()
            error_message = repr(e)
            event_vo = {
                'event_key': md5_hash,
                'event_type': 'ERROR',
                'severity': 'CRITICAL',
                'resource': {},
                'description': error_message,
                'title': 'AmorePacific Parsing ERROR',
                'rule': '',
                'occurred_at': datetime.now(),
                'additional_info': {}
            }
            event_result_model = EventModel(event_vo, strict=False)
            event_result_model.validate()
            event_result_model_native = event_result_model.to_native()
            default_parsed_data_list.append(event_result_model_native)

        return default_parsed_data_list

    @staticmethod
    def _occurred_at(raw_data):
        current_time = datetime.now()
        occurred_at = raw_data.get('event_time', current_time)
        parsed_occurred_at = None
        try:
            if isinstance(occurred_at, datetime):
                parsed_occurred_at = occurred_at
            else:
                timestamp_str = occurred_at.split(' ')
                if len(timestamp_str) != 2:
                    parsed_occurred_at = current_time
                else:
                    date_object = datetime.strptime(f'{timestamp_str[0]}T{timestamp_str[1]}', _TIMESTAMP_FORMAT)
                    parsed_occurred_at = date_object
        except Exception as e:
            parsed_occurred_at = datetime.now()

        _LOGGER.debug(f'[EventManager] _occurred_at : {parsed_occurred_at}')
        return parsed_occurred_at

    @staticmethod
    def _parse_summary(raw_data):
        parsed_summary = {
            'title': raw_data.get('summary', ''),
            'body': raw_data.get('conditionlog', '')
        }
        return parsed_summary
