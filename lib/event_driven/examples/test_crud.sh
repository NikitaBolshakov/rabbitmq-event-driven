echo "Creating user"
curl -X POST "http://127.0.0.1:8000/users/"     -H "Content-Type: application/json"     -d '{
      "username": "cooluser",
      "email": "cool.user@example.com",
      "full_name": "Cool User Name"
    }'
echo ""
echo "Getting user"
curl -X GET "http://127.0.0.1:8000/users/1"
echo ""
echo "Updating user"
curl -X PUT "http://127.0.0.1:8000/users/1"     -H "Content-Type: application/json"     -d '{
      "user_id": 1,
      "username": "cooluser2"
    }'
echo ""
echo "Deleting user"
curl -X DELETE "http://127.0.0.1:8000/users/1"
echo ""