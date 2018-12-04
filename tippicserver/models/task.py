
from sqlalchemy_utils import ArrowType

from tippicserver import db


class Task(db.Model):
    """the Task class represent a single task"""
    task_id = db.Column(db.String(40), nullable=False, primary_key=True)
    task_type = db.Column(db.String(40), nullable=False, primary_key=True)
    title = db.Column(db.String(80), nullable=False, primary_key=False)
    desc = db.Column(db.String(200), nullable=False, primary_key=False)
    price = db.Column(db.Integer(), nullable=False, primary_key=False)
    video_url = db.Column(db.String(100), nullable=True, primary_key=False)
    min_to_complete = db.Column(db.Float(), nullable=False, primary_key=False)
    provider_data = db.Column(db.JSON)
    tags = db.Column(db.JSON)
    items = db.Column(db.JSON)
    start_date = db.Column(ArrowType)
    update_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())
    delay_days = db.Column(db.Integer(), nullable=False, primary_key=False)
    min_client_version_android = db.Column(db.String(80), nullable=False, primary_key=False)
    min_client_version_ios = db.Column(db.String(80), nullable=False, primary_key=False)
    post_task_actions = db.Column(db.JSON)

    def __repr__(self):
        return '<task_id: %s, task_type: %s, title: %s, desc: %s, price: %s, video_url: %s, min_to_complete: %s, start_date: %s, delay_days: %s, min_client_version_android: %s, min_client_version_ios %s>' % \
               (self.task_id, self.task_type, self.title, self.desc, self.price, self.video_url, self.min_to_complete, self.start_data, self.delay_days, self.min_client_version_android, self.min_client_version_ios)

