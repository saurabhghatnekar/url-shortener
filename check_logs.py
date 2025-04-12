from app import app, db, RequestLog

with app.app_context():
    print(f'Request logs count: {RequestLog.query.count()}')
    for log in RequestLog.query.all():
        print(f'Log: {log.method} {log.path} from {log.ip_address} at {log.timestamp} - Response time: {log.response_time}s')
