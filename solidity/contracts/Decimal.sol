pragma solidity ^0.4.24;

import './SafeMath.sol';

/**
presented by: https://github.com/raineorshine/sol-decimal

A Solidity Decimal type.

Usage:
import "./Decimal.sol";
contract A {
  using Decimal for Decimal.Data;

  function foo() public constant returns(uint) {
    Decimal.Data memory a = Decimal.fromUint(5);
    Decimal.Data memory b = Decimal.Data({
      num: 12,
      den: 3
    });

    return a.add(b).toUint(); // 9
  }
}

*/
library Decimal {

    using SafeMath for uint256;

    /** Creates a Decimal Data from a uint numerator and uint denominator by directly constructing Data. */
    struct Data {
        uint num; // numerator
        uint den; // denomenator
    }

    // A decimal value can store multiples of 1/DECIMAL_DIVISOR
    uint256 public constant DECIMAL_DIVISOR = 10 ** 10;

    /** Creates a Decimal Data from a uint. */
    function fromUint(uint256 num) internal pure returns (Data memory) {
        return Data({
            num : num,
            den : 1
            });
    }

    function fromSignDecimal(int168 num) internal pure returns (Data memory) {
        return fromDecimal(uint256(num));
    }

    /** Creates a Decimal Data from a Decimal bytes. */
    function fromDecimal(uint256 num) internal pure returns (Data memory) {
        return Data({
            num : num,
            den : DECIMAL_DIVISOR
            });
    }

    /** Converts a Decimal to a uint (effectively flooring the value). **/
    function toUint(Data memory self) internal pure returns (uint256) {
        require(self.den > 0, "invalid zero divide.");
        return self.num.div(self.den);
    }

    /** Converts to decimal by increasing up 10 digitsnum. the decimal is fi168x10 **/
    function toDecimal(Data memory self) internal pure returns (int168) {
        require(self.den > 0, "invalid zero divide.");
        if (int256(self.num) < 0) {
            // is signed Decimal
            return int168(self.num / self.den * DECIMAL_DIVISOR);
        }
        return int168(self.num.mul(DECIMAL_DIVISOR).div(self.den));
    }

    /** Adds two Decimals without loss of precision. */
    function add(Data memory a, Data memory b) internal pure returns (Data memory) {

        Data memory result;
        if (a.den == b.den) {
            result.den = a.den;
            if (int256(a.num) < 0 || int256(b.num) < 0) {
                // it is sign Decimal calculation
                result.num = a.num + b.num;
            } else {
                result.num = a.num.add(b.num);
            }
        } else {
            result.den = a.den.mul(b.den);
            if (int256(a.num) < 0 || int256(b.num) < 0) {
                // it is sign Decimal calculation
                result.num = a.num.mul(b.den) + b.num.mul(a.den);
            } else {
                result.num = a.num.mul(b.den).add(b.num.mul(a.den));
            }
        }
        return result;
    }

    /** Subtracts two Decimals without loss of precision. */
    function sub(Data memory a, Data memory b) internal pure returns (Data memory) {
        Data memory result;
        if (a.den == b.den) {
            // if same denomenator, use b.num as-is
            result.num = a.num.sub(b.num);
            result.den = a.den;
        } else {
            // otherwise convert (b) to the same denominator as (a)
            result.num = a.num.mul(b.den).sub(b.num.mul(a.den));
            result.den = a.den.mul(b.den);
        }
        return compacting(result);
    }

    /** Sign-Subtracts two Decimals without loss of precision.  it will be have overflow. SO, CAREFULLY!!*/
    function ssub(Data memory a, Data memory b) internal pure returns (Data memory) {
        Data memory result;
        if (a.den == b.den) {
            // if same denomenator, use b.num as-is
            result.num = a.num - b.num;
            result.den = a.den;
        } else {
            // otherwise convert (b) to the same denominator as (a)
            result.num = a.num.mul(b.den) - (b.num.mul(a.den));
            result.den = a.den.mul(b.den);
        }
        return compacting(result);
    }

    /** Multiplies two Decimals without loss of precision. */
    function mul(Data memory a, Data memory b) internal pure returns (Data memory) {
        // bypass overflow. it is temporary workaround.... TODO: It exec only if it happend oveflow.
        a = fromSignDecimal(toDecimal(a));
        b = fromSignDecimal(toDecimal(b));
        if (int256(a.num) < 0 || int256(b.num) < 0) {
            // sign decimal
            return compacting(Data({
                num : uint(int256(a.num) * int256(b.num)), // allow overflow. TODO: Check safety.
                den : a.den.mul(b.den)
                }));
        } else {
            return compacting(Data({
                num : a.num.mul(b.num),
                den : a.den.mul(b.den)
                }));
        }
    }

    /** Divides two Decimals without loss of precision. */
    function div(Data memory a, Data memory b) internal pure returns (Data memory) {
        uint u_num = a.num.mul(b.den);
        uint u_den = b.num.mul(a.den);
        return compacting(Data({
            num : u_num,
            den : u_den
            }));
    }

    function compacting(Data memory self) internal pure returns (Data memory) {
        uint _gcd = gcd(self.num, self.den);
        return Data({
            num : self.num.div(_gcd),
            den : self.den.div(_gcd)
            });
    }

    /**
     * @dev Compare a to b.
     * @return 0 is a < b
     *         1 is a = b
     *         2 is a > b
     */
    function comp(Data memory a, Data memory b) internal pure returns (uint8) {
        uint a_num = a.num * b.den;
        uint b_num = b.num * a.den;
        if (a_num < b_num) {
            return 0;
        } else if (a_num == b_num) {
            return 1;
        } else {
            return 2;
        }
    }

    /**
     * @dev Compare a to 0.
     * @return 0 is a < 0
     *         1 is a = 0
     *         2 is a > 0
     */
    function compZero(Data memory a) internal pure returns (uint8) {
        if (a.num < 0) {
            return 0;
        } else if (a.num == 0) {
            return 1;
        } else {
            return 2;
        }
    }

    /**
     * @dev greatest common divisor. Using Euclidean Algorithm.
     */
    function gcd(uint a, uint b) internal pure returns (uint) {
        (uint min, uint max) = sort(a, b);
        if (min == 0) {
            return max;
        }
        uint mod = max % min;

        while (mod > 0) {
            (min, max) = sort(mod, min);
            mod = max % min;
        }
        return min;
    }

    /**
     * @dev least common multiple
     */
    function lcm(uint a, uint b) internal pure returns (uint) {
        uint _gcd = gcd(a, b);
        if (_gcd == 1) {
            return a.mul(b);
        }
        return a.div(_gcd).mul(b.div(_gcd)).mul(_gcd);
    }

    function sort(uint a, uint b) internal pure returns (uint, uint) {
        return a < b ? (a, b) : (b, a);
    }
}