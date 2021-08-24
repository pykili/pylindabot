from bot import models


def test_get_staff(db):
    teacher = models.BotUser.objects.create(
        first_name='ivan',
        last_name='pupkin',
        role=models.BotUserRole.Teacher.value,
    )
    student = models.BotUser.objects.create(
        first_name='ivan',
        last_name='pupkin',
        role=models.BotUserRole.Student.value,
    )
    group = models.Groups.objects.create(id=202, name='test group')
    group.users.add(student, teacher)

    submission = models.Submission(
        author=student,
        assignment_type=models.AssignmentType.Homework.value,
        assignment_id=1,
        task_id=1,
        status=models.SubmissionStatus.Pending.value,
        objectkey='none',
    )

    staff = submission.get_staff()

    assert len(staff) == 1
    assert staff[0].id == teacher.id
