% ---------- Statutory rules (simplified to what the case needs) ----------

% carry_on_limit(L,W,H).
carry_on_limit(22,14,9).

% personal_item_limit(L,W,H).
personal_item_limit(18,14,8).

% base_checked_fee(CheckedIndex, Fee).     % Basic-Economy, within U.S.
base_checked_fee(1,40).
base_checked_fee(2,45).
base_checked_fee(3,150).
base_checked_fee(N,200) :- N>=4.

% oversize_fee(SizeInches, Fee)  (within U.S.)
oversize_fee(Size,0   ) :- Size =< 62.
oversize_fee(Size,30  ) :- Size > 62 , Size =< 65.
oversize_fee(Size,200 ) :- Size > 65 , Size =< 115.
oversize_fee(Size,na  ) :- Size > 115.              % not accepted - not used here

% overweight_fee(WeightLbs, Fee)  (within U.S.)
overweight_fee(W,0  ) :- W =< 50.
overweight_fee(W,30 ) :- W > 50 , W =< 53.
overweight_fee(W,100) :- W > 53 , W =< 70.
overweight_fee(W,200) :- W > 70 , W =< 100.
overweight_fee(W,na ) :- W > 100.                   % not accepted - not used here

% surcharge(Weight,Size,Fee) - higher of over-weight / over-size
surcharge(W,S,Fee) :-
    overweight_fee(W,OF),
    oversize_fee(S,OS),
    max_fee(OF,OS,Fee).

max_fee(na,na,na).
max_fee(na,X,X) :- X \= na.
max_fee(X,na,X) :- X \= na.
max_fee(X,Y,X)  :- X>=Y.
max_fee(X,Y,Y)  :- Y>X.

% ----------------------- Facts for this case -----------------------------

% bag(Id, length, width, height, weight).
bag(1,21,14, 6,  7).
bag(2,36,19, 9, 53).
bag(3,38,18, 9, 53).
bag(4,36,15,13, 51).
bag(5,50,27,25, 86).

ticket_price(164).

% --------------- Helper predicates to classify each item -----------------

dims_ok(L,W,H, MaxL,MaxW,MaxH) :-
    L =< MaxL, W =< MaxW, H =< MaxH.

qualifies_personal(Id) :-
    bag(Id,L,W,H,_),
    personal_item_limit(PL,PW,PH),
    dims_ok(L,W,H,PL,PW,PH).

qualifies_carryon(Id) :-
    bag(Id,L,W,H,_),
    carry_on_limit(CL,CW,CH),
    dims_ok(L,W,H,CL,CW,CH).

% choose one free carry-on (there is exactly one that fits)
free_carryon(Id) :-
    qualifies_carryon(Id),
    \+ qualifies_personal(Id).        % none of the bags is small enough for personal item

% checked(Id) : every bag that is not the free carry-on
checked(Id) :-
    bag(Id,_,_,_,_),
    \+ free_carryon(Id).

% -------------------- Fee computation for each bag -----------------------

checked_bag_list(List) :-
    findall(Id,checked(Id),Uns),
    sort(Uns,List).   % get deterministic order  [2,3,4,5]

checked_base_fee(Id,Fee) :-
    checked_bag_list(List),
    nth1(Index,List,Id),
    base_checked_fee(Index,Fee).

bag_size(Id,Size) :-
    bag(Id,L,W,H,_),
    Size is L+W+H.

bag_weight(Id,W) :-
    bag(Id,_,_,_,W).

bag_surcharge(Id,SFee) :-
    bag_weight(Id,W),
    bag_size(Id,Size),
    surcharge(W,Size,SFee).

bag_total_fee(Id,Total) :-
    checked_base_fee(Id,Base),
    bag_surcharge(Id,SFee),
    Total is Base + SFee.

% -------------------------- Grand total ----------------------------------

checked_total(T) :-
    findall(Fee, (checked(Id), bag_total_fee(Id,Fee)), Fees),
    sum_list(Fees,T).

total_cost(Total) :-
    ticket_price(TP),
    checked_total(CT),
    Total is TP + CT.

% ------------------------------ Query ------------------------------------
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.