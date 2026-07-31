from fastapi.testclient import TestClient
from app.main import app

def test_backend_flow():
    with TestClient(app) as client:
        # 1. Login Super Admin
        login_res = client.post("/api/v1/auth/login", json={
            "email": "admin@mess.com",
            "password": "admin123"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        data = login_res.json()
        assert "access_token" in data
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create User
        user_res = client.post("/api/v1/users", headers=headers, json={
            "name": "John Doe",
            "email": "john@mess.com",
            "password": "password123",
            "role": "MEMBER"
        })
        assert user_res.status_code in [201, 400], f"Create user failed: {user_res.text}"

        # 3. Assign Manager
        assign_res = client.post("/api/v1/months/assign-manager", headers=headers, json={
            "user_id": 1
        })
        assert assign_res.status_code == 200, f"Assign manager failed: {assign_res.text}"

        # 4. Add Grocery Expense
        exp_res = client.post("/api/v1/expenses", headers=headers, json={
            "amount": 1200.0,
            "description": "Weekly grocery shopping"
        })
        assert exp_res.status_code == 201, f"Expense failed: {exp_res.text}"

        # 5. Batch Daily Meals
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        meal_res = client.post("/api/v1/meals/batch", headers=headers, json={
            "date": today_str,
            "meals": [
                {"user_id": 1, "lunch_count": 1, "dinner_count": 2}
            ]
        })
        assert meal_res.status_code == 200, f"Meal batch failed: {meal_res.text}"

        # 6. Add Member Deposit
        dep_res = client.post("/api/v1/deposits", headers=headers, json={
            "user_id": 1,
            "amount": 1500.0
        })
        assert dep_res.status_code == 201, f"Deposit failed: {dep_res.text}"

        # 7. Check Summary Calculation
        summary_res = client.get("/api/v1/summary", headers=headers)
        assert summary_res.status_code == 200, f"Summary failed: {summary_res.text}"
        s_data = summary_res.json()
        print("\nSummary Result:", s_data)
        assert s_data["total_expenses"] == 1200.0
        assert s_data["total_meals"] == 3
        assert s_data["meal_rate"] == 400.0  # 1200 / 3

if __name__ == "__main__":
    test_backend_flow()
    print("\nALL BACKEND API TESTS PASSED SUCCESSFULLY!")
